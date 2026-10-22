from __future__ import annotations

import base64
import hashlib
import os
import queue
import socket
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .chunking import read_in_chunks, sha256_hex
from .protocol import ProtocolError, receive_message, send_message


class IntegrityError(Exception):
    pass


class DownloadCancelled(Exception):
    pass


@dataclass
class ProgressEvent:
    kind: str
    chunk_count: int
    bytes_done: int
    file_size: int
    file_name: str
    index: int | None = None
    message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


ProgressCallback = Callable[[ProgressEvent], None]


class P2PClient:
    def __init__(
        self,
        host: str,
        port: int,
        timeout_s: float = 20.0,
        connections: int = 4,
        retries: int = 3,
        chunk_delay_s: float = 0.0,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.connections = max(1, connections)
        self.retries = max(0, retries)
        self.chunk_delay_s = chunk_delay_s

    def _open(self) -> tuple[socket.socket, object]:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout_s)
        return sock, sock.makefile("r", encoding="utf-8")

    def _ask(self, message: dict) -> dict:
        sock, file = self._open()
        with sock:
            send_message(sock, message)
            return receive_message(file)

    def list_files(self) -> list[dict]:
        response = self._ask({"type": "GET_CATALOG"})
        if not response.get("ok"):
            raise ProtocolError(response.get("error", "unable to fetch catalog"))
        return response["files"]

    def refresh(self) -> int:
        response = self._ask({"type": "REFRESH"})
        if not response.get("ok"):
            raise ProtocolError(response.get("error", "refresh failed"))
        return int(response["count"])

    def download(
        self,
        file_id: str,
        destination: Path,
        on_progress: ProgressCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> Path:
        destination = Path(destination)
        part = destination.with_name(destination.name + ".part")
        emit_lock = threading.Lock()
        state = {"bytes_done": 0, "chunk_count": 0, "file_size": 0, "file_name": destination.name}

        def emit(kind: str, index: int | None = None, message: str | None = None) -> None:
            if on_progress is None:
                return
            with emit_lock:
                event = ProgressEvent(kind, state["chunk_count"], state["bytes_done"],
                                      state["file_size"], state["file_name"], index, message)
                try:
                    on_progress(event)
                except Exception:
                    pass

        try:
            manifest = self._fetch_manifest(file_id)
            state.update(chunk_count=len(manifest["chunk_hashes"]), file_size=manifest["file_size"],
                         file_name=manifest["file_name"])
            emit("manifest")
            self._transfer(manifest, destination, part, state, emit, emit_lock, cancel)
            emit("done")
            return destination
        except DownloadCancelled:
            emit("cancelled", message="Download cancelled")
            raise
        except Exception as exc:
            emit("error", message=str(exc) or exc.__class__.__name__)
            raise

    def _fetch_manifest(self, file_id: str) -> dict:
        reply = self._ask({"type": "GET_MANIFEST", "file_id": file_id})
        if not reply.get("ok"):
            raise FileNotFoundError(reply.get("error", "manifest missing"))
        return reply["manifest"]

    def _transfer(self, manifest, destination, part, state, emit, emit_lock, cancel) -> None:
        hashes: list[str] = manifest["chunk_hashes"]
        chunk_size: int = manifest["chunk_size"]
        file_size: int = manifest["file_size"]
        destination.parent.mkdir(parents=True, exist_ok=True)

        done: set[int] = set()
        if part.exists() and part.stat().st_size == file_size:
            with part.open("rb") as handle:
                for index, expected in enumerate(hashes):
                    if sha256_hex(handle.read(chunk_size)) == expected:
                        done.add(index)
        else:
            with part.open("wb") as handle:
                handle.truncate(file_size)

        if done:
            state["bytes_done"] = sum(min(chunk_size, file_size - i * chunk_size) for i in done)
            emit("resumed", message=f"{len(done)} chunks already verified")

        pending: queue.Queue[int] = queue.Queue()
        for index in range(len(hashes)):
            if index not in done:
                pending.put(index)

        abort = threading.Event()
        errors: list[BaseException] = []
        write_lock = threading.Lock()

        with part.open("r+b") as handle:

            def worker() -> None:
                try:
                    sock, file = self._open()
                except BaseException as exc:
                    errors.append(exc)
                    abort.set()
                    return
                with sock:
                    while not abort.is_set():
                        if cancel is not None and cancel.is_set():
                            abort.set()
                            return
                        try:
                            index = pending.get_nowait()
                        except queue.Empty:
                            return
                        try:
                            chunk = self._fetch_chunk(sock, file, manifest, index, emit)
                            with write_lock:
                                handle.seek(index * chunk_size)
                                handle.write(chunk)
                            with emit_lock:
                                state["bytes_done"] += len(chunk)
                            emit("chunk_ok", index)
                        except BaseException as exc:
                            errors.append(exc)
                            abort.set()
                            return
                        if self.chunk_delay_s:
                            time.sleep(self.chunk_delay_s)

            threads = [threading.Thread(target=worker, daemon=True)
                       for _ in range(min(self.connections, pending.qsize()))]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        if errors:
            raise errors[0]
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled()

        emit("verifying", message="Checking the whole file")
        whole = hashlib.sha256()
        for block in read_in_chunks(part, 1024 * 1024):
            whole.update(block)
        if whole.hexdigest() != manifest["file_hash"]:
            part.unlink(missing_ok=True)
            raise IntegrityError("File hash mismatch")
        os.replace(part, destination)

    def _fetch_chunk(self, sock, file, manifest, index: int, emit) -> bytes:
        attempts = self.retries + 1
        expected = manifest["chunk_hashes"][index]
        for attempt in range(1, attempts + 1):
            send_message(sock, {"type": "GET_CHUNK", "file_id": manifest["file_id"], "index": index})
            reply = receive_message(file)
            if not reply.get("ok"):
                raise FileNotFoundError(reply.get("error", "chunk missing"))
            chunk = base64.b64decode(reply["data_b64"])
            if sha256_hex(chunk) == expected:
                return chunk
            emit("chunk_failed", index,
                 f"Chunk {index} failed its hash check (attempt {attempt} of {attempts})")
        raise IntegrityError(f"Chunk {index} failed its hash check after {attempts} attempts")

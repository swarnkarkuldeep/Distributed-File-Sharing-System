from __future__ import annotations

import base64
import socket
import threading
import time
from pathlib import Path
from typing import Callable

from .protocol import (
    ConnectionClosedError,
    MessageTooLargeError,
    ProtocolError,
    receive_message,
    send_message,
)
from .storage import SharedLibrary
from .tamper import TamperControl

MAX_CHUNK_SIZE = 2 * 1024 * 1024


class P2PPeerServer:
    def __init__(
        self,
        share_dir: str | Path,
        host: str = "0.0.0.0",
        port: int = 9000,
        chunk_size: int = 256 * 1024,
        on_event: Callable[[dict], None] | None = None,
        idle_timeout_s: float = 120.0,
    ) -> None:
        if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
            raise ValueError(f"chunk_size must be between 1 and {MAX_CHUNK_SIZE}")
        self.host = host
        self.port = port
        self.idle_timeout_s = idle_timeout_s
        self.library = SharedLibrary(Path(share_dir), chunk_size=chunk_size)
        self.tamper = TamperControl()
        self.ready = threading.Event()
        self.bound_port = port
        self._on_event = on_event
        self._shutdown = threading.Event()

    def _emit(self, kind: str, remote: str, **fields) -> None:
        if self._on_event is None:
            return
        event = {"type": "peer", "kind": kind, "ts": time.time(), "remote": remote,
                 "file_id": None, "file_name": None, "index": None, "chunk_count": None}
        event.update(fields)
        try:
            self._on_event(event)
        except Exception:
            pass

    def start(self) -> None:
        self.library.refresh()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen()
            server.settimeout(0.25)
            self.bound_port = server.getsockname()[1]
            print(f"Peer listening on {self.host}:{self.bound_port}. Shared files: {len(self.library.catalog())}")
            self.ready.set()

            while not self._shutdown.is_set():
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                worker = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                worker.start()

    def stop(self) -> None:
        self._shutdown.set()

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        remote = f"{addr[0]}:{addr[1]}"
        self._emit("connect", remote)
        with conn:
            conn.settimeout(self.idle_timeout_s)
            conn_file = conn.makefile("r", encoding="utf-8")
            try:
                while True:
                    try:
                        message = receive_message(conn_file)
                    except (ConnectionClosedError, MessageTooLargeError):
                        raise
                    except ProtocolError as exc:
                        send_message(conn, {"type": "ERROR", "ok": False, "error": str(exc)})
                        continue
                    try:
                        self._dispatch(conn, remote, message)
                    except (ValueError, TypeError, KeyError) as exc:
                        send_message(conn, {"type": "ERROR", "ok": False, "error": f"bad request: {exc}"})
            except (ConnectionError, OSError, ProtocolError):
                pass
            finally:
                self._emit("disconnect", remote)

    def _dispatch(self, conn: socket.socket, remote: str, message: dict) -> None:
        msg_type = message.get("type")

        if msg_type == "GET_CATALOG":
            send_message(conn, {"type": "CATALOG", "ok": True, "files": self.library.catalog()})
            self._emit("catalog", remote)
            return

        if msg_type == "GET_MANIFEST":
            file_id = str(message.get("file_id", ""))
            manifest = self.library.get_manifest(file_id)
            if not manifest:
                send_message(conn, {"type": "MANIFEST", "ok": False, "error": "file not found"})
            else:
                send_message(conn, {"type": "MANIFEST", "ok": True, "manifest": manifest.to_dict()})
                self._emit("manifest", remote, file_id=file_id, file_name=manifest.file_name,
                           chunk_count=manifest.chunk_count)
            return

        if msg_type == "GET_CHUNK":
            file_id = str(message.get("file_id", ""))
            raw_index = message.get("index", -1)
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise ValueError("index must be an integer")
            index = raw_index
            result = self.library.get_chunk(file_id, index)
            if not result:
                send_message(conn, {"type": "CHUNK", "ok": False, "error": "chunk not found"})
                return
            data, chunk_hash = result
            data, tampered = self.tamper.apply(file_id, index, data)
            send_message(
                conn,
                {
                    "type": "CHUNK",
                    "ok": True,
                    "index": index,
                    "chunk_hash": chunk_hash,
                    "data_b64": base64.b64encode(data).decode("ascii"),
                },
            )
            manifest = self.library.get_manifest(file_id)
            fields = dict(file_id=file_id, index=index,
                          file_name=manifest.file_name if manifest else None,
                          chunk_count=manifest.chunk_count if manifest else None)
            self._emit("tamper_served" if tampered else "chunk", remote, **fields)
            return

        if msg_type == "REFRESH":
            self.library.refresh()
            send_message(conn, {"type": "REFRESHED", "ok": True, "count": len(self.library.catalog())})
            self._emit("refresh", remote)
            return

        send_message(conn, {"type": "ERROR", "ok": False, "error": f"unsupported message: {msg_type}"})

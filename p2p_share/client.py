from __future__ import annotations

import base64
import socket
from pathlib import Path

from .chunking import sha256_hex
from .protocol import ProtocolError, receive_message, send_message


class IntegrityError(Exception):
    pass


class P2PClient:
    def __init__(self, host: str, port: int, timeout_s: float = 20.0) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s

    def list_files(self) -> list[dict]:
        with socket.create_connection((self.host, self.port), timeout=self.timeout_s) as sock:
            file = sock.makefile("r", encoding="utf-8")
            send_message(sock, {"type": "GET_CATALOG"})
            response = receive_message(file)
            if not response.get("ok"):
                raise ProtocolError(response.get("error", "unable to fetch catalog"))
            return response["files"]

    def download(self, file_id: str, destination: Path) -> Path:
        with socket.create_connection((self.host, self.port), timeout=self.timeout_s) as sock:
            file = sock.makefile("r", encoding="utf-8")

            send_message(sock, {"type": "GET_MANIFEST", "file_id": file_id})
            manifest_reply = receive_message(file)
            if not manifest_reply.get("ok"):
                raise FileNotFoundError(manifest_reply.get("error", "manifest missing"))

            manifest = manifest_reply["manifest"]
            expected_file_hash = manifest["file_hash"]
            destination.parent.mkdir(parents=True, exist_ok=True)

            chunks: list[bytes] = []
            for index, expected_chunk_hash in enumerate(manifest["chunk_hashes"]):
                send_message(sock, {"type": "GET_CHUNK", "file_id": file_id, "index": index})
                chunk_reply = receive_message(file)
                if not chunk_reply.get("ok"):
                    raise FileNotFoundError(chunk_reply.get("error", "chunk missing"))

                chunk = base64.b64decode(chunk_reply["data_b64"])
                if sha256_hex(chunk) != expected_chunk_hash:
                    raise IntegrityError(f"Chunk {index} hash mismatch")
                chunks.append(chunk)

            payload = b"".join(chunks)
            if sha256_hex(payload) != expected_file_hash:
                raise IntegrityError("File hash mismatch")

            destination.write_bytes(payload)
            return destination

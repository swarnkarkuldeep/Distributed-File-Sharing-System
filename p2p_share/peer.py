from __future__ import annotations

import base64
import socket
import threading
from pathlib import Path

from .protocol import ProtocolError, receive_message, send_message
from .storage import SharedLibrary


class P2PPeerServer:
    def __init__(
        self,
        share_dir: str | Path,
        host: str = "0.0.0.0",
        port: int = 9000,
        chunk_size: int = 256 * 1024,
    ) -> None:
        self.host = host
        self.port = port
        self.library = SharedLibrary(Path(share_dir), chunk_size=chunk_size)
        self._shutdown = threading.Event()

    def start(self) -> None:
        self.library.refresh()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen()
            print(f"Peer listening on {self.host}:{self.port}. Shared files: {len(self.library.catalog())}")

            while not self._shutdown.is_set():
                conn, addr = server.accept()
                worker = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
                worker.start()

    def stop(self) -> None:
        self._shutdown.set()

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        with conn:
            conn_file = conn.makefile("r", encoding="utf-8")
            try:
                while True:
                    message = receive_message(conn_file)
                    msg_type = message.get("type")

                    if msg_type == "GET_CATALOG":
                        send_message(conn, {"type": "CATALOG", "ok": True, "files": self.library.catalog()})
                        continue

                    if msg_type == "GET_MANIFEST":
                        file_id = message.get("file_id", "")
                        manifest = self.library.get_manifest(file_id)
                        if not manifest:
                            send_message(conn, {"type": "MANIFEST", "ok": False, "error": "file not found"})
                        else:
                            send_message(conn, {"type": "MANIFEST", "ok": True, "manifest": manifest.to_dict()})
                        continue

                    if msg_type == "GET_CHUNK":
                        file_id = message.get("file_id", "")
                        index = int(message.get("index", -1))
                        result = self.library.get_chunk(file_id, index)
                        if not result:
                            send_message(conn, {"type": "CHUNK", "ok": False, "error": "chunk not found"})
                        else:
                            data, chunk_hash = result
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
                        continue

                    if msg_type == "REFRESH":
                        self.library.refresh()
                        send_message(conn, {"type": "REFRESHED", "ok": True, "count": len(self.library.catalog())})
                        continue

                    send_message(conn, {"type": "ERROR", "ok": False, "error": f"unsupported message: {msg_type}"})
            except (ConnectionError, OSError, ProtocolError):
                print(f"Connection closed for {addr[0]}:{addr[1]}")

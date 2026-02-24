from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

from p2p_share.client import P2PClient
from p2p_share.peer import P2PPeerServer


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_end_to_end_download(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir()
    source_file = shared / "hello.txt"
    source_file.write_text("distributed systems are fun\n" * 200, encoding="utf-8")

    port = get_free_port()
    server = P2PPeerServer(shared, host="127.0.0.1", port=port, chunk_size=128)

    worker = threading.Thread(target=server.start, daemon=True)
    worker.start()
    time.sleep(0.25)

    client = P2PClient("127.0.0.1", port)
    catalog = client.list_files()
    assert len(catalog) == 1

    file_id = catalog[0]["file_id"]
    output = tmp_path / "downloads" / "copy.txt"
    client.download(file_id, output)

    assert output.read_bytes() == source_file.read_bytes()

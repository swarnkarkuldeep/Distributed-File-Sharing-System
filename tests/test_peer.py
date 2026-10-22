from __future__ import annotations

import base64
import hashlib
import socket
import threading
import time
from pathlib import Path

import pytest

from p2p_share.peer import P2PPeerServer
from p2p_share.protocol import MAX_LINE_BYTES, receive_message, send_message


class Conn:
    def __init__(self, port: int) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.file = self.sock.makefile("r", encoding="utf-8")

    def ask(self, message: dict) -> dict:
        send_message(self.sock, message)
        return receive_message(self.file)

    def close(self) -> None:
        self.file.close()
        self.sock.close()


@pytest.fixture
def server(tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "hello.txt").write_bytes(b"0123456789" * 30)
    events: list[dict] = []
    srv = P2PPeerServer(shared, host="127.0.0.1", port=0, chunk_size=64, on_event=events.append)
    srv.events = events  # type: ignore[attr-defined]
    thread = threading.Thread(target=srv.start, daemon=True)
    thread.start()
    assert srv.ready.wait(5)
    yield srv
    srv.stop()
    thread.join(5)


def file_id(srv: P2PPeerServer) -> str:
    return srv.library.catalog()[0]["file_id"]


def test_string_index_gets_error_reply_and_connection_survives(server):
    c = Conn(server.bound_port)
    reply = c.ask({"type": "GET_CHUNK", "file_id": file_id(server), "index": "abc"})
    assert reply["ok"] is False and reply["type"] == "ERROR"
    assert c.ask({"type": "GET_CATALOG"})["ok"] is True
    c.close()


def test_json_array_gets_error_reply(server):
    c = Conn(server.bound_port)
    c.sock.sendall(b"[1,2]\n")
    reply = receive_message(c.file)
    assert reply["ok"] is False and reply["type"] == "ERROR"
    assert c.ask({"type": "GET_CATALOG"})["ok"] is True
    c.close()


def test_oversized_line_closes_connection_server_keeps_serving(server):
    c = Conn(server.bound_port)
    try:
        c.sock.sendall(b"x" * (MAX_LINE_BYTES + 10))
    except OSError:
        pass
    c.close()
    other = Conn(server.bound_port)
    assert other.ask({"type": "GET_CATALOG"})["ok"] is True
    other.close()


def test_idle_connection_is_closed(tmp_path: Path):
    srv = P2PPeerServer(tmp_path, host="127.0.0.1", port=0, idle_timeout_s=0.2)
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    assert srv.ready.wait(5)
    sock = socket.create_connection(("127.0.0.1", srv.bound_port), timeout=5)
    time.sleep(0.6)
    try:
        assert sock.recv(10) == b""
    except ConnectionResetError:
        pass
    sock.close()
    srv.stop()
    t.join(5)


def test_stop_unblocks_start(tmp_path: Path):
    srv = P2PPeerServer(tmp_path, host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    assert srv.ready.wait(5)
    srv.stop()
    t.join(3)
    assert not t.is_alive()


@pytest.mark.parametrize("size", [0, -1, 2 * 1024 * 1024 + 1])
def test_chunk_size_validation(tmp_path: Path, size: int):
    with pytest.raises(ValueError):
        P2PPeerServer(tmp_path, chunk_size=size)


def test_events_emitted_for_catalog_and_chunk(server):
    c = Conn(server.bound_port)
    c.ask({"type": "GET_CATALOG"})
    c.ask({"type": "GET_CHUNK", "file_id": file_id(server), "index": 1})
    c.close()
    time.sleep(0.1)
    kinds = [e["kind"] for e in server.events]
    assert "connect" in kinds and "catalog" in kinds and "chunk" in kinds
    chunk = next(e for e in server.events if e["kind"] == "chunk")
    assert chunk["index"] == 1 and chunk["chunk_count"] == 5 and chunk["file_name"] == "hello.txt"
    assert chunk["remote"].startswith("127.0.0.1:")


def test_tampered_chunk_served_with_true_hash(server):
    fid = file_id(server)
    server.tamper.arm(fid, 0, once=True)
    c = Conn(server.bound_port)
    first = c.ask({"type": "GET_CHUNK", "file_id": fid, "index": 0})
    second = c.ask({"type": "GET_CHUNK", "file_id": fid, "index": 0})
    c.close()
    h = lambda r: hashlib.sha256(base64.b64decode(r["data_b64"])).hexdigest()
    assert h(first) != first["chunk_hash"]
    assert h(second) == second["chunk_hash"]
    assert any(e["kind"] == "tamper_served" for e in server.events)


def test_line_limit_counts_bytes_not_characters(server):
    # Just over the limit in bytes, but a quarter of it in characters (each emoji is 4 bytes of UTF-8).
    c = Conn(server.bound_port)
    payload = ("\U0001F600" * (MAX_LINE_BYTES // 4 + 1000)).encode("utf-8") + b"\n"
    try:
        c.sock.sendall(payload)
    except OSError:
        pass
    c.sock.settimeout(10)
    try:
        data = c.sock.recv(1024)
    except ConnectionResetError:
        data = b""
    assert data == b""  # closed, not answered with an ERROR reply
    c.close()
    other = Conn(server.bound_port)
    assert other.ask({"type": "GET_CATALOG"})["ok"] is True
    other.close()


def test_a_big_manifest_fits_in_one_message(tmp_path: Path):
    assert MAX_LINE_BYTES == 16 * 1024 * 1024

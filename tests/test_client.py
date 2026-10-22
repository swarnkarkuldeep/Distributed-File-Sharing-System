from __future__ import annotations

import hashlib
import socket
import threading
import time
from pathlib import Path

import pytest

from p2p_share.client import DownloadCancelled, IntegrityError, P2PClient, ProgressEvent
from p2p_share.peer import P2PPeerServer
from p2p_share.protocol import ProtocolError, receive_message, send_message

CHUNK = 128
DATA = b"distributed systems are fun\n" * 200  # 5600 bytes -> 44 chunks of 128


@pytest.fixture
def served(tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    src = shared / "hello.txt"
    src.write_bytes(DATA)
    events: list[dict] = []
    srv = P2PPeerServer(shared, host="127.0.0.1", port=0, chunk_size=CHUNK, on_event=events.append)
    srv.events = events  # type: ignore[attr-defined]
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    assert srv.ready.wait(5)
    yield srv, shared, tmp_path
    srv.stop()
    t.join(5)


def fid(srv) -> str:
    return srv.library.catalog()[0]["file_id"]


def collect():
    events: list[ProgressEvent] = []
    return events, events.append


def test_parallel_download_matches_source(served):
    srv, _, tmp = served
    out = tmp / "out" / "copy.txt"
    P2PClient("127.0.0.1", srv.bound_port, connections=4).download(fid(srv), out)
    assert out.read_bytes() == DATA
    assert not out.with_name("copy.txt.part").exists()


def test_each_chunk_reported_ok_exactly_once(served):
    srv, _, tmp = served
    events, cb = collect()
    P2PClient("127.0.0.1", srv.bound_port, connections=4).download(fid(srv), tmp / "c.txt", on_progress=cb)
    ok = sorted(e.index for e in events if e.kind == "chunk_ok")
    assert ok == list(range(44))
    assert events[0].kind == "manifest" and events[-1].kind == "done"
    assert events[-1].bytes_done == len(DATA)
    assert "verifying" in [e.kind for e in events]


def test_empty_file_downloads(tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "empty.bin").write_bytes(b"")
    srv = P2PPeerServer(shared, host="127.0.0.1", port=0, chunk_size=CHUNK)
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    assert srv.ready.wait(5)
    out = tmp_path / "empty-copy.bin"
    P2PClient("127.0.0.1", srv.bound_port).download(fid(srv), out)
    assert out.read_bytes() == b""
    srv.stop()
    t.join(5)


def test_tamper_once_is_caught_and_healed(served):
    srv, _, tmp = served
    srv.tamper.arm(fid(srv), 5, once=True)
    events, cb = collect()
    out = tmp / "healed.txt"
    P2PClient("127.0.0.1", srv.bound_port).download(fid(srv), out, on_progress=cb)
    assert out.read_bytes() == DATA
    failed = [e for e in events if e.kind == "chunk_failed"]
    assert len(failed) == 1 and failed[0].index == 5


def test_tamper_persistent_fails_after_retries(served):
    srv, _, tmp = served
    srv.tamper.arm(fid(srv), 5, once=False)
    out = tmp / "never.txt"
    with pytest.raises(IntegrityError):
        P2PClient("127.0.0.1", srv.bound_port, retries=2).download(fid(srv), out)
    assert not out.exists()


def test_resume_skips_valid_chunks(served):
    srv, _, tmp = served
    out = tmp / "resume.txt"
    part = tmp / "resume.txt.part"
    part.write_bytes(DATA[: 22 * CHUNK] + b"\x00" * (len(DATA) - 22 * CHUNK))
    events, cb = collect()
    P2PClient("127.0.0.1", srv.bound_port).download(fid(srv), out, on_progress=cb)
    assert out.read_bytes() == DATA
    resumed = next(e for e in events if e.kind == "resumed")
    assert resumed.bytes_done == 22 * CHUNK
    time.sleep(0.1)
    assert len([e for e in srv.events if e["kind"] == "chunk"]) == 44 - 22


def test_cancel_raises_and_keeps_part(served):
    srv, _, tmp = served
    cancel = threading.Event()

    def cb(e: ProgressEvent) -> None:
        if e.kind == "chunk_ok":
            cancel.set()

    out = tmp / "cancel.txt"
    events = []
    with pytest.raises(DownloadCancelled):
        P2PClient("127.0.0.1", srv.bound_port, connections=1, chunk_delay_s=0.01).download(
            fid(srv), out, on_progress=lambda e: (events.append(e), cb(e)), cancel=cancel
        )
    assert not out.exists()
    assert (tmp / "cancel.txt.part").exists()
    assert events[-1].kind == "cancelled"


def test_unreachable_peer_raises_oserror_quickly(tmp_path: Path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    start = time.time()
    with pytest.raises(OSError):
        P2PClient("127.0.0.1", port, timeout_s=1).download("abc", tmp_path / "x")
    assert time.time() - start < 3


def test_unknown_file_raises_file_not_found(served):
    srv, _, tmp = served
    with pytest.raises(FileNotFoundError):
        P2PClient("127.0.0.1", srv.bound_port).download("0" * 64, tmp / "x")


def test_peer_dropping_mid_download_emits_error_and_keeps_part(tmp_path: Path):
    chunks = [DATA[i : i + CHUNK] for i in range(0, 5 * CHUNK, CHUNK)]
    body = b"".join(chunks)
    manifest = {
        "file_id": hashlib.sha256(body).hexdigest(), "file_name": "f.bin", "file_size": len(body),
        "chunk_size": CHUNK, "chunk_hashes": [hashlib.sha256(c).hexdigest() for c in chunks],
        "file_hash": hashlib.sha256(body).hexdigest(), "chunk_count": 5,
    }
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def handle(conn: socket.socket) -> None:
        import base64
        f = conn.makefile("r", encoding="utf-8")
        try:
            while True:
                m = receive_message(f)
                if m["type"] == "GET_MANIFEST":
                    send_message(conn, {"type": "MANIFEST", "ok": True, "manifest": manifest})
                elif m["index"] < 1:
                    send_message(conn, {"type": "CHUNK", "ok": True, "index": 0,
                                        "chunk_hash": manifest["chunk_hashes"][0],
                                        "data_b64": base64.b64encode(chunks[0]).decode()})
                else:
                    return
        except (ProtocolError, OSError):
            pass
        finally:
            conn.close()

    def serve() -> None:
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    events, cb = collect()
    out = tmp_path / "drop.bin"
    with pytest.raises((OSError, ProtocolError)):
        P2PClient("127.0.0.1", listener.getsockname()[1], connections=1, timeout_s=2).download(
            manifest["file_id"], out, on_progress=cb
        )
    listener.close()
    assert events[-1].kind == "error"
    assert not out.exists() and (tmp_path / "drop.bin.part").exists()


def test_chunk_delay_slows_download(served):
    srv, _, tmp = served
    start = time.time()
    P2PClient("127.0.0.1", srv.bound_port, connections=1, chunk_delay_s=0.01).download(fid(srv), tmp / "slow.txt")
    assert time.time() - start >= 0.4


def test_refresh_picks_up_new_file(served):
    srv, shared, _ = served
    (shared / "second.txt").write_text("another file")
    client = P2PClient("127.0.0.1", srv.bound_port)
    assert len(client.list_files()) == 1
    assert client.refresh() == 2
    assert len(client.list_files()) == 2

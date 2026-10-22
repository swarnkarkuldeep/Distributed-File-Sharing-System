from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.settings import PeerRef, Settings
from p2p_share.peer import P2PPeerServer

DATA = b"downloader api test data\n" * 40  # 1000 bytes -> 16 chunks of 64


@pytest.fixture
def peer(tmp_path: Path):
    shared = tmp_path / "peer-shared"
    shared.mkdir()
    (shared / "x.txt").write_bytes(DATA)
    srv = P2PPeerServer(shared, host="127.0.0.1", port=0, chunk_size=64)
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    assert srv.ready.wait(5)
    yield srv
    srv.stop()
    t.join(5)


def dead_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def client(tmp_path: Path, peer):
    settings = Settings(
        role="downloader",
        download_dir=tmp_path / "downloads",
        peers=[PeerRef("Test peer", "127.0.0.1", peer.bound_port), PeerRef("Dead peer", "127.0.0.1", dead_port())],
    )
    with TestClient(create_app(settings)) as c:
        yield c


def file_id(peer) -> str:
    return peer.library.catalog()[0]["file_id"]


def wait_for(client, predicate, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for event in client.app.state.bus.history_since(0):
            if predicate(event):
                return event
        time.sleep(0.02)
    raise AssertionError("timed out waiting for event")


def start(client, peer, **extra) -> str:
    body = {"peer": "Test peer", "file_id": file_id(peer), **extra}
    r = client.post("/downloads", json=body)
    assert r.status_code == 202, r.text
    return r.json()["download_id"]


def events_for(client, download_id):
    return [e for e in client.app.state.bus.history_since(0) if e.get("download_id") == download_id]


def test_download_flow_publishes_ordered_events_and_saves_file(client, peer):
    did = start(client, peer)
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "done")
    evs = events_for(client, did)
    assert evs[0]["kind"] == "manifest" and evs[-1]["kind"] == "done"
    assert sum(e["kind"] == "chunk_ok" for e in evs) == 16
    assert evs[-1]["bytes_done"] == len(DATA)
    assert client.get("/saved").json() == [{"name": "x.txt", "size": len(DATA)}]
    assert client.get("/saved/x.txt").content == DATA


def test_two_downloads_run_concurrently(client, peer):
    a = start(client, peer, chunk_delay_ms=20)
    b = start(client, peer, chunk_delay_ms=20)
    for did in (a, b):
        wait_for(client, lambda e, did=did: e.get("download_id") == did and e["kind"] == "done")
    names = sorted(f["name"] for f in client.get("/saved").json())
    assert names == ["x (2).txt", "x.txt"]


def test_cancel_publishes_cancelled(client, peer):
    did = start(client, peer, connections=1, chunk_delay_ms=100)
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "chunk_ok")
    assert client.delete(f"/downloads/{did}").status_code == 202
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "cancelled")
    assert client.get("/saved").json() == []


def test_cancel_unknown_download_404(client):
    assert client.delete("/downloads/nope").status_code == 404


def test_unreachable_peer_returns_502_quickly(client, peer):
    started = time.time()
    r = client.post("/downloads", json={"peer": f"127.0.0.1:{dead_port()}", "file_id": file_id(peer)})
    assert r.status_code == 502 and "127.0.0.1" in r.json()["detail"]
    assert time.time() - started < 5


def test_unknown_file_404(client):
    r = client.post("/downloads", json={"peer": "Test peer", "file_id": "0" * 64})
    assert r.status_code == 404


def test_peers_reports_reachable_flag(client):
    peers = {p["label"]: p for p in client.get("/peers").json()}
    assert peers["Test peer"]["reachable"] is True and peers["Test peer"]["file_count"] == 1
    assert peers["Dead peer"]["reachable"] is False


def test_peer_files_lists_catalog_and_502_when_down(client, peer):
    files = client.get("/peers/files", params={"peer": "Test peer"}).json()
    assert files[0]["file_name"] == "x.txt"
    assert client.get("/peers/files", params={"peer": "Dead peer"}).status_code == 502


def test_saved_rejects_path_traversal(client, tmp_path: Path):
    (tmp_path / "secret.txt").write_text("top secret")
    for url in ("/saved/..%2fsecret.txt", "/saved/%2e%2e%2fsecret.txt", "/saved/../secret.txt"):
        r = client.get(url)
        assert r.status_code == 404 and b"top secret" not in r.content
    assert client.delete("/saved/..%2fsecret.txt").status_code == 404
    assert (tmp_path / "secret.txt").exists()


def test_chunk_delay_applied(client, peer):
    did = start(client, peer, connections=1, chunk_delay_ms=20)
    done = wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "done")
    first = events_for(client, did)[0]
    assert done["ts"] - first["ts"] >= 0.25


def test_tampered_chunk_shows_chunk_failed_then_done(client, peer):
    peer.tamper.arm(file_id(peer), 3, once=True)
    did = start(client, peer)
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "done")
    kinds = [e["kind"] for e in events_for(client, did)]
    assert "chunk_failed" in kinds and kinds.index("chunk_failed") < kinds.index("done")
    assert client.get("/saved/x.txt").content == DATA


def test_delete_saved(client, peer):
    did = start(client, peer)
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "done")
    assert client.delete("/saved/x.txt").status_code == 204
    assert client.get("/saved").json() == []


def test_failed_download_leaves_no_part_file(client, peer, tmp_path: Path):
    peer.tamper.arm(file_id(peer), 3, once=False)
    did = start(client, peer, connections=1)
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "error")
    time.sleep(0.2)
    assert list((tmp_path / "downloads").iterdir()) == []


def test_cancelled_download_leaves_no_part_file(client, peer, tmp_path: Path):
    did = start(client, peer, connections=1, chunk_delay_ms=100)
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "chunk_ok")
    client.delete(f"/downloads/{did}")
    wait_for(client, lambda e: e.get("download_id") == did and e["kind"] == "cancelled")
    time.sleep(0.2)
    assert list((tmp_path / "downloads").iterdir()) == []

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.settings import Settings
from p2p_share.client import P2PClient


def make_client(tmp_path: Path, **overrides) -> TestClient:
    settings = Settings(role="uploader", share_dir=tmp_path / "shared", download_dir=tmp_path / "dl",
                        peer_port=0, chunk_size=64, **overrides)
    return TestClient(create_app(settings))


@pytest.fixture
def client(tmp_path: Path):
    with make_client(tmp_path) as c:
        yield c


def upload(client: TestClient, name: str, data: bytes):
    return client.post("/files", files={"file": (name, data, "application/octet-stream")})


def test_health_and_status(client):
    assert client.get("/health").json() == {"ok": True, "role": "uploader"}
    status = client.get("/status").json()
    assert status["role"] == "uploader" and status["file_count"] == 0 and status["tamper"] is None
    assert status["peer_port"] == client.app.state.peer.bound_port


def test_upload_lists_and_serves_over_tcp(client, tmp_path: Path):
    data = b"hello over tcp " * 40
    r = upload(client, "hello.txt", data)
    assert r.status_code == 201
    entry = r.json()
    assert entry["file_name"] == "hello.txt" and entry["chunk_count"] == 10
    assert [e["file_id"] for e in client.get("/files").json()] == [entry["file_id"]]
    out = tmp_path / "got.txt"
    P2PClient("127.0.0.1", client.app.state.peer.bound_port).download(entry["file_id"], out)
    assert out.read_bytes() == data


def test_hostile_filename_stays_inside_share_dir(client, tmp_path: Path):
    r1 = upload(client, "../../evil.txt", b"one")
    r2 = upload(client, ".hidden", b"two")
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["file_name"] == "evil.txt"
    assert r2.json()["file_name"] == "hidden"
    assert not (tmp_path / "evil.txt").exists()
    assert (tmp_path / "shared" / "evil.txt").exists()


def test_same_name_twice_gets_suffix(client):
    upload(client, "hello.txt", b"first")
    r = upload(client, "hello.txt", b"second")
    assert r.json()["file_name"] == "hello (2).txt"
    assert len(client.get("/files").json()) == 2


def test_same_bytes_new_name_becomes_alias(client):
    upload(client, "a.txt", b"identical")
    r = upload(client, "b.txt", b"identical")
    assert r.status_code == 201
    files = client.get("/files").json()
    assert len(files) == 1 and files[0]["aliases"] == ["b.txt"]


def test_empty_file_upload(client):
    r = upload(client, "empty.bin", b"")
    assert r.status_code == 201 and r.json()["chunk_count"] == 0


def test_oversized_upload_413(tmp_path: Path):
    with make_client(tmp_path, max_upload_mb=1) as c:
        r = upload(c, "big.bin", b"\x00" * (1024 * 1024 + 10))
        assert r.status_code == 413
        assert c.get("/files").json() == []
        assert [p for p in (tmp_path / "shared").iterdir()] == []


def test_delete_file(client):
    fid = upload(client, "a.txt", b"bye").json()["file_id"]
    assert client.delete(f"/files/{fid}").status_code == 204
    assert client.get("/files").json() == []
    assert client.delete(f"/files/{fid}").status_code == 404


def test_tamper_arm_and_disarm_roundtrip(client):
    fid = upload(client, "a.txt", b"x" * 200).json()["file_id"]
    r = client.put("/tamper", json={"file_id": fid, "index": 1, "once": True})
    assert r.status_code == 200 and r.json() == {"file_id": fid, "index": 1, "once": True}
    assert client.get("/status").json()["tamper"]["index"] == 1
    assert client.delete("/tamper").status_code == 200
    assert client.get("/status").json()["tamper"] is None


def test_tamper_unknown_file_404_and_bad_index_422(client):
    fid = upload(client, "a.txt", b"x" * 200).json()["file_id"]
    assert client.put("/tamper", json={"file_id": "nope", "index": 0}).status_code == 404
    assert client.put("/tamper", json={"file_id": fid, "index": 99}).status_code == 422


def test_events_history_contains_file_added(client):
    upload(client, "a.txt", b"event")
    events = client.app.state.bus.history_since(0)
    added = [e for e in events if e["type"] == "file" and e["kind"] == "added"]
    assert added and added[0]["file"]["file_name"] == "a.txt"


def test_seed_sample_shared_on_start(tmp_path: Path):
    with make_client(tmp_path, seed_sample=True) as c:
        files = c.get("/files").json()
        assert [f["file_name"] for f in files] == ["demo-sample-1.bin"]
        assert files[0]["file_size"] == 2 * 1024 * 1024


def test_concurrent_same_name_uploads_never_overwrite(tmp_path: Path, monkeypatch):
    import threading
    import time

    import api.uploader as uploader_module

    original = uploader_module.unique_path

    def slow_unique_path(*args, **kwargs):
        chosen = original(*args, **kwargs)
        time.sleep(0.15)  # widen the check-then-act window so a race shows up every time
        return chosen

    monkeypatch.setattr(uploader_module, "unique_path", slow_unique_path)
    with make_client(tmp_path) as c:
        results: list = []

        def go(i: int) -> None:
            results.append(upload(c, "same.txt", f"content {i}".encode()))

        threads = [threading.Thread(target=go, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert [r.status_code for r in results] == [201] * 6
        assert len({r.json()["file_name"] for r in results}) == 6
        assert len(c.get("/files").json()) == 6
        assert len([p for p in (tmp_path / "shared").iterdir()]) == 6


def test_default_chunk_size_follows_the_size_class(tmp_path: Path):
    settings = Settings(role="uploader", share_dir=tmp_path / "shared", download_dir=tmp_path / "dl", peer_port=0)
    with TestClient(create_app(settings)) as c:
        entry = upload(c, "a.bin", b"x" * (100 * 1024)).json()
        assert entry["chunk_size"] == 16 * 1024 and entry["chunk_count"] == 7
        assert "chunk_hashes" not in entry
        assert c.get("/status").json()["chunk_size"] is None

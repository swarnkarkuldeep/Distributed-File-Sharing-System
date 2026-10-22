import hashlib
import threading
import tracemalloc
from pathlib import Path

from p2p_share.chunking import build_manifest
from p2p_share.storage import SharedLibrary


def test_empty_file_manifest(tmp_path: Path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    m = build_manifest(f, 1024)
    assert m.chunk_count == 0
    assert m.file_hash == hashlib.sha256(b"").hexdigest()
    assert m.file_size == 0


def test_manifest_streams_without_loading_file(tmp_path: Path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"\xab" * (8 * 1024 * 1024))
    tracemalloc.start()
    m = build_manifest(f, 64 * 1024)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert m.chunk_count == 128
    assert peak < 1024 * 1024


def test_duplicate_content_becomes_alias(tmp_path: Path):
    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")
    lib = SharedLibrary(tmp_path, 1024)
    lib.refresh()
    entries = lib.catalog()
    assert len(entries) == 1
    assert entries[0]["file_name"] == "a.txt"
    assert entries[0]["aliases"] == ["b.txt"]


def test_hidden_and_directories_ignored(tmp_path: Path):
    (tmp_path / ".secret").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "ok.txt").write_text("ok")
    lib = SharedLibrary(tmp_path, 1024)
    lib.refresh()
    assert [e["file_name"] for e in lib.catalog()] == ["ok.txt"]


def test_get_chunk_detects_file_changed_on_disk(tmp_path: Path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello world" * 10)
    lib = SharedLibrary(tmp_path, 16)
    lib.refresh()
    fid = lib.catalog()[0]["file_id"]
    assert lib.get_chunk(fid, 0) is not None
    f.write_bytes(b"HELLO WORLD" * 10)
    assert lib.get_chunk(fid, 0) is None


def test_refresh_never_hides_files_from_readers(tmp_path: Path):
    (tmp_path / "a.txt").write_text("a" * 100)
    lib = SharedLibrary(tmp_path, 16)
    lib.refresh()
    fid = lib.catalog()[0]["file_id"]
    stop = threading.Event()

    def refresher():
        while not stop.is_set():
            lib.refresh()

    t = threading.Thread(target=refresher)
    t.start()
    try:
        for _ in range(2000):
            assert lib.get_manifest(fid) is not None
    finally:
        stop.set()
        t.join()


def test_add_and_remove_file(tmp_path: Path):
    lib = SharedLibrary(tmp_path, 16)
    lib.refresh()
    f = tmp_path / "new.txt"
    f.write_text("new content")
    m = lib.add_file(f)
    assert lib.get_manifest(m.file_id) is not None
    assert lib.remove_file(m.file_id) is True
    assert not f.exists()
    assert lib.get_manifest(m.file_id) is None
    assert lib.remove_file(m.file_id) is False

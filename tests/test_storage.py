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


def test_chunk_size_classes():
    from p2p_share.chunking import chunk_size_for

    mib = 1024 * 1024
    assert chunk_size_for(0) == 16 * 1024
    assert chunk_size_for(4 * mib) == 16 * 1024
    assert chunk_size_for(4 * mib + 1) == 256 * 1024
    assert chunk_size_for(256 * mib) == 256 * 1024
    assert chunk_size_for(256 * mib + 1) == mib
    assert chunk_size_for(2048 * mib) == mib
    assert chunk_size_for(2048 * mib + 1) == 2 * mib
    assert chunk_size_for(10_000 * mib) == 2 * mib


def test_manifest_defaults_to_the_size_class(tmp_path: Path):
    small = tmp_path / "small.bin"
    small.write_bytes(b"x" * (100 * 1024))
    medium = tmp_path / "medium.bin"
    medium.write_bytes(b"y" * (5 * 1024 * 1024))
    assert build_manifest(small).chunk_size == 16 * 1024
    assert build_manifest(small).chunk_count == 7
    assert build_manifest(medium).chunk_size == 256 * 1024
    assert build_manifest(medium).chunk_count == 20


def test_library_without_fixed_size_is_adaptive_and_fixed_size_still_overrides(tmp_path: Path):
    (tmp_path / "a.bin").write_bytes(b"z" * (100 * 1024))
    adaptive = SharedLibrary(tmp_path)
    adaptive.refresh()
    assert adaptive.catalog()[0]["chunk_size"] == 16 * 1024
    fixed = SharedLibrary(tmp_path, chunk_size=64 * 1024)
    fixed.refresh()
    assert fixed.catalog()[0]["chunk_size"] == 64 * 1024


def test_catalog_entries_omit_the_chunk_hash_list(tmp_path: Path):
    (tmp_path / "a.bin").write_bytes(b"q" * 1000)
    lib = SharedLibrary(tmp_path, 100)
    lib.refresh()
    entry = lib.catalog()[0]
    assert "chunk_hashes" not in entry
    assert entry["chunk_count"] == 10 and entry["file_hash"] == entry["file_id"]
    assert len(lib.get_manifest(entry["file_id"]).chunk_hashes) == 10

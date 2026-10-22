from __future__ import annotations

import argparse
import threading
from pathlib import Path

import pytest

from p2p_share import cli
from p2p_share.peer import P2PPeerServer


def test_parse_peer_rejects_non_numeric_port():
    with pytest.raises(argparse.ArgumentTypeError):
        cli.parse_peer("localhost:abc")


def test_parse_peer_rejects_missing_port():
    with pytest.raises(argparse.ArgumentTypeError):
        cli.parse_peer("localhost")


def test_parse_peer_accepts_ipv4_host_port():
    assert cli.parse_peer("127.0.0.1:9000") == ("127.0.0.1", 9000)


@pytest.fixture
def served(tmp_path: Path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "a.txt").write_bytes(b"cli test data " * 100)
    srv = P2PPeerServer(shared, host="127.0.0.1", port=0, chunk_size=128)
    t = threading.Thread(target=srv.start, daemon=True)
    t.start()
    assert srv.ready.wait(5)
    yield srv, shared, tmp_path
    srv.stop()
    t.join(5)


def test_cli_download_end_to_end(served, monkeypatch, capsys):
    srv, shared, tmp = served
    fid = srv.library.catalog()[0]["file_id"]
    out = tmp / "out.txt"
    monkeypatch.setattr("sys.argv", ["p2p", "download", f"127.0.0.1:{srv.bound_port}", fid, str(out),
                                     "--connections", "2", "--retries", "1"])
    cli.main()
    assert out.read_bytes() == (shared / "a.txt").read_bytes()
    assert "Downloaded to" in capsys.readouterr().out


def test_cli_refresh_prints_count(served, monkeypatch, capsys):
    srv, shared, _ = served
    (shared / "b.txt").write_text("more")
    monkeypatch.setattr("sys.argv", ["p2p", "refresh", f"127.0.0.1:{srv.bound_port}"])
    cli.main()
    assert "2 files" in capsys.readouterr().out

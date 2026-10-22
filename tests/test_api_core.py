from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from api.events import EventBus
from api.seed import seed_sample
from api.settings import PeerRef, Settings


def test_settings_parse_peers():
    s = Settings.from_env({
        "ROLE": "downloader",
        "PEERS": "Uploader=uploader:9000,Uploader 2=uploader2:9001,bare:9002",
        "CHUNK_SIZE": "16384",
        "SEED_SAMPLE": "1",
    })
    assert s.role == "downloader"
    assert s.chunk_size == 16384
    assert s.seed_sample is True
    assert s.peers == [
        PeerRef("Uploader", "uploader", 9000),
        PeerRef("Uploader 2", "uploader2", 9001),
        PeerRef("bare:9002", "bare", 9002),
    ]


def test_settings_defaults():
    s = Settings.from_env({})
    assert s.role == "uploader" and s.peer_port == 9000 and s.chunk_size == 256 * 1024
    assert s.peers == [] and s.seed_sample is False and s.max_upload_mb == 512


def test_bus_assigns_increasing_seq_and_trims_history():
    bus = EventBus(history=3)
    for i in range(5):
        bus.publish({"type": "x", "i": i})
    hist = bus.history_since(0)
    assert [e["i"] for e in hist] == [2, 3, 4]
    assert [e["seq"] for e in hist] == [3, 4, 5]
    assert all("ts" in e for e in hist)


def test_history_since_returns_only_newer():
    bus = EventBus()
    for i in range(4):
        bus.publish({"type": "x", "i": i})
    assert [e["i"] for e in bus.history_since(2)] == [2, 3]


def test_publish_from_other_thread_reaches_stream():
    bus = EventBus()
    bus.publish({"type": "x", "i": 0})

    async def run():
        got = []
        stream = bus.stream(0)
        got.append(await stream.__anext__())  # history replay
        threading.Timer(0.1, lambda: bus.publish({"type": "x", "i": 1})).start()
        got.append(await asyncio.wait_for(stream.__anext__(), 3))
        await stream.aclose()
        return got

    got = asyncio.run(run())
    assert [e["i"] for e in got] == [0, 1]
    assert [e["seq"] for e in got] == [1, 2]


def test_stream_resumes_after_last_seq_without_duplicates():
    bus = EventBus()
    for i in range(3):
        bus.publish({"type": "x", "i": i})

    async def run():
        stream = bus.stream(2)
        first = await asyncio.wait_for(stream.__anext__(), 3)
        await stream.aclose()
        return first

    assert asyncio.run(run())["i"] == 2


def test_seed_is_deterministic_and_skips_nonempty_dir(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    pa = seed_sample(a, "s.bin", 5000, seed=1)
    pb = seed_sample(b, "s.bin", 5000, seed=1)
    assert pa.read_bytes() == pb.read_bytes() and pa.stat().st_size == 5000
    assert seed_sample(a, "other.bin", 5000, seed=2) is None
    assert not (a / "other.bin").exists()

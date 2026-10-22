"""Compare fixed chunk sizes with the size-class chunk sizes on this machine.

    python scripts/bench.py                       # 4 MiB, 64 MiB and 512 MiB synthetic files
    python scripts/bench.py --sizes 16 256        # sizes in MiB
    python scripts/bench.py --file path/to/big.mkv

Everything runs on localhost in one process: a real peer server and the real parallel client,
so the numbers show protocol and chunking overhead, not network speed. Prints a Markdown table.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

from p2p_share.chunking import build_manifest, chunk_size_for
from p2p_share.client import P2PClient
from p2p_share.peer import P2PPeerServer

MIB = 1024 * 1024
POLICIES: list[tuple[str, int | None]] = [("fixed 16 KiB", 16 * 1024), ("fixed 256 KiB", 256 * 1024), ("size class", None)]


def make_file(path: Path, size: int) -> None:
    with path.open("wb") as handle:
        remaining = size
        while remaining:
            block = min(remaining, 8 * MIB)
            handle.write(os.urandom(block))
            remaining -= block


def human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    raise AssertionError


def bench_one(source: Path, chunk_size: int | None, connections: int) -> dict:
    size = source.stat().st_size

    started = time.perf_counter()
    manifest = build_manifest(source, chunk_size)
    manifest_s = time.perf_counter() - started
    manifest_bytes = len(json.dumps(manifest.to_dict(), separators=(",", ":")))

    work = Path(tempfile.mkdtemp(prefix="bench-"))
    try:
        shared = work / "shared"
        shared.mkdir()
        os.link(source, shared / source.name) if os.name != "nt" else shutil.copyfile(source, shared / source.name)
        server = P2PPeerServer(shared, host="127.0.0.1", port=0, chunk_size=chunk_size)
        thread = threading.Thread(target=server.start, daemon=True)
        thread.start()
        server.ready.wait(60)
        file_id = server.library.catalog()[0]["file_id"]

        started = time.perf_counter()
        P2PClient("127.0.0.1", server.bound_port, connections=connections).download(file_id, work / "out.bin")
        download_s = time.perf_counter() - started
        server.stop()
        thread.join(5)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    return {
        "chunk_size": manifest.chunk_size,
        "chunks": manifest.chunk_count,
        "manifest_bytes": manifest_bytes,
        "manifest_s": manifest_s,
        "download_s": download_s,
        "mib_per_s": size / MIB / download_s if download_s else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", type=int, nargs="*", default=[4, 64, 512], help="synthetic file sizes in MiB")
    parser.add_argument("--file", type=Path, help="benchmark this existing file instead of synthetic ones")
    parser.add_argument("--connections", type=int, default=4)
    args = parser.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="bench-src-"))
    try:
        if args.file:
            sources = [args.file]
        else:
            sources = []
            for mib in args.sizes:
                path = scratch / f"synthetic-{mib}MiB.bin"
                make_file(path, mib * MIB)
                sources.append(path)

        print(f"{args.connections} parallel connections, localhost, one process.\n")
        print("| File | Chunking | Chunk size | Chunks | Hash list on the wire | Hashing | Download | Throughput |")
        print("|---|---|---|---|---|---|---|---|")
        for source in sources:
            size = source.stat().st_size
            for name, chunk_size in POLICIES:
                r = bench_one(source, chunk_size, args.connections)
                label = f"{name} ({human(chunk_size_for(size))})" if chunk_size is None else name
                print(
                    f"| {source.name if args.file else human(size)} | {label} | {human(r['chunk_size'])} | "
                    f"{r['chunks']:,} | {human(r['manifest_bytes'])} | {r['manifest_s']:.1f} s | "
                    f"{r['download_s']:.1f} s | {r['mib_per_s']:.0f} MiB/s |",
                    flush=True,
                )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()

# Chunk size benchmarks

What chunk size does to a transfer, measured with `python scripts/bench.py`.

**How it was measured:** one Windows 11 laptop, one process, localhost, 4 parallel connections, a real peer server and the real client. Each row is a single run, so differences under about 10% are noise. This shows protocol and chunking overhead, not network speed. Hashing time on the 1.7 GB file's first row also includes reading it cold from disk, so compare its download times, not its hashing times.

## Results

| File | Chunking | Chunk size | Chunks | Hash list on the wire | Download | Throughput |
|---|---|---|---|---|---|---|
| 64 MiB | fixed 16 KiB | 16 KiB | 4,096 | 268 KiB | 2.6 s | 24 MiB/s |
| 64 MiB | fixed 256 KiB | 256 KiB | 256 | 17 KiB | 1.3 s | 49 MiB/s |
| 64 MiB | **size class** | 256 KiB | 256 | 17 KiB | 0.9 s | 68 MiB/s |
| 512 MiB | fixed 16 KiB | 16 KiB | 32,768 | 2.1 MiB | 22.7 s | 23 MiB/s |
| 512 MiB | fixed 256 KiB | 256 KiB | 2,048 | 134 KiB | 15.0 s | 34 MiB/s |
| 512 MiB | **size class** | 1 MiB | 512 | 34 KiB | 15.7 s | 33 MiB/s |
| 1.7 GB movie | fixed 16 KiB | 16 KiB | 106,735 | **6.8 MiB** | 50.9 s | 33 MiB/s |
| 1.7 GB movie | fixed 256 KiB | 256 KiB | 6,671 | 437 KiB | 33.9 s | 49 MiB/s |
| 1.7 GB movie | **size class** | 1 MiB | 1,668 | **109 KiB** | 34.4 s | 49 MiB/s |

(4 MiB files are 0.1 s whichever way they are chunked, so they are left out.)

## What it shows

- **Tiny chunks are the problem.** Against the old fixed 16 KiB, the size classes make the 1.7 GB file's hash list 62 times smaller (6.8 MiB to 109 KiB) and its download about a third faster (50.9 s to 34.4 s). Every chunk is one request and one response, and 106,735 of them is a lot of round trips.
- **A 6.8 MiB hash list used to be a hard failure.** The old protocol refused any message over 4 MiB, so the movie could not be listed at all. The limit is now 16 MiB, counted in bytes, and the file list no longer carries hash lists.
- **The size classes are not faster than a fixed 256 KiB.** They are within noise of it for large files. What the 1 MiB class buys over 256 KiB is a hash list four times smaller (109 KiB against 437 KiB), not speed.
- **The ceiling is Python, not chunking.** Throughput levels off around 50 MiB/s on this machine, because base64 encoding, JSON and per-chunk hashing run in Python.
- **Small files keep many chunks on purpose.** A 2 MB demo file stays at 16 KiB chunks (128 tiles) so the demo has something to show. The size classes trade a little speed on small files for that.

Run it yourself:

```bash
python scripts/bench.py                      # 4, 64 and 512 MiB synthetic files
python scripts/bench.py --sizes 16 256       # sizes in MiB
python scripts/bench.py --file path/to/big.bin
```

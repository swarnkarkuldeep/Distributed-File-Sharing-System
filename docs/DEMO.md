# Five-minute demo

Before you start: `docker compose up`, then open <http://localhost:8080>.

## Set the stage (30 seconds)

1. Click **Open the uploader window**, then **Open the downloader window**.
2. Snap the uploader to the left half of your screen and the downloader to the right half.
3. In the downloader, drag **Demo speed** to about 60 ms. Without a pause, a local transfer is over before anyone sees it.

## 1. A normal transfer (1 minute)

- Uploader: it already shares `demo-sample-1.bin`. Drop in a file of your own too.
- Downloader: under **Files on Uploader**, click **Download**.
- Point at the tiles filling in. Each one lights up only after that chunk's SHA-256 matched the hash the uploader promised. The counters show how many are verified.
- When it finishes: **Downloaded and verified**, with the whole-file hash. Click **Save to this computer** to show the file leaving the container.
- Back in the uploader, the mosaic and the activity list show exactly what was served.

## 2. Catch a corrupted chunk (1 minute)

- Uploader, **Corrupt a chunk**: leave the chunk number where it is and click **Corrupt this chunk once**.
- Downloader: download the same file again.
- Watch for one tile flashing red and fading back to lit, and **Failed hash checks** showing 1. The downloader rejected the bad bytes, asked again, and still finished with a verified file.
- Try **Corrupt every time** to show what happens when a peer keeps sending bad data: the download fails with a clear message instead of saving a broken file.

## 3. Choose a peer (1 minute)

- Downloader, **Peer**: click **Uploader 2**. It shares a different sample file.
- Download from it. Two peers, one downloader, nothing central.
- Open <http://localhost:8080/uploader2> in a third window to share more files from the second peer.

## 4. Speed and parallelism (1 minute)

- Set **Demo speed** to Instant and download again: it finishes almost immediately.
- Set **Parallel connections** to 1, then 8, with a pause per chunk. Tiles fill out of order with more connections because chunks arrive on several connections at once.

## 5. The same thing from a terminal (30 seconds)

```bash
python -m p2p_share.cli list 127.0.0.1:9000
```

The command line talks to the same peer the browser uses.

## If something looks wrong

- A window says it can't reach the app server: check `docker compose ps`. All four containers should be running.
- A peer shows as offline: its container may still be starting. Click **Refresh list**.
- The list of finished transfers shows old downloads after a page reload. That is the event history replaying. Restart the `downloader` container to clear it.

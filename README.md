# Chunkway: peer-to-peer file sharing with verified chunks

Share a file in one browser window and watch it arrive, chunk by chunk, in another. Every chunk is checked against its SHA-256 hash on arrival, and the whole file is checked again before it is saved. You can corrupt a chunk on purpose and watch the downloader catch it and fetch it again.

The core is a small Python peer-to-peer protocol (standard library only). A web demo (React + Vite, glass-style UI) and a one-command Docker setup sit on top of it.

## Run the demo

You need Docker Desktop. From this folder:

```bash
docker compose up
```

Then open <http://localhost:8080> and click **Open the uploader window** and **Open the downloader window**. Put the two windows side by side.

Four containers start:

| Container | What it does | Host port |
|---|---|---|
| `web` | The React app, served by nginx | 8080 (this machine only) |
| `uploader` | A peer sharing files, plus its API | 9000 (peer protocol, this machine only) |
| `uploader2` | A second peer, so the downloader has a choice | 9001 (peer protocol, this machine only) |
| `downloader` | The downloading side, plus its API | none |

Each uploader starts with a 2 MB sample file, so there is something to download straight away. Chunks are 16 KiB in the demo, so that file shows 128 tiles. See [docs/DEMO.md](docs/DEMO.md) for a five-minute walkthrough.

Stop with `Ctrl+C`. `docker compose down -v` also deletes the shared files.

## What you can do in the windows

- **Uploader:** drop files to share them, watch which chunks the downloader takes, and corrupt a chunk on purpose.
- **Downloader:** pick a peer (Uploader or Uploader 2, or type `host:port`), download a file, and watch every chunk light up as its hash is verified. The **Demo speed** slider adds a pause per chunk. Without it, a local transfer finishes in milliseconds. Finished files can be saved to your computer from the browser.

## The command line still works

The demo publishes the uploaders' peer ports, so the CLI can talk to them (Python 3.10 or newer, no dependencies):

```bash
python -m p2p_share.cli list 127.0.0.1:9000
python -m p2p_share.cli download 127.0.0.1:9000 <FILE_ID> ./downloads/file.bin
python -m p2p_share.cli refresh 127.0.0.1:9000
```

Or run your own peer from a folder:

```bash
mkdir shared downloads
python -m p2p_share.cli serve ./shared --host 0.0.0.0 --port 9000
```

`download` accepts `--connections N` (parallel connections, default 4) and `--retries N` (retries per corrupted chunk, default 3). If a download stops partway, running the same command again resumes from the `.part` file next to the output path.

## How it works

```
Browser window 1  /uploader   ─┐                         ┌─ uploader   API ── TCP peer :9000 ◄──┐
                               ├─► web (nginx :8080) ───►├─ uploader2  API ── TCP peer :9000    │ peer protocol
Browser window 2  /downloader ─┘   serves the app,       └─ downloader API ── P2PClient ────────┘
                                   proxies /api/<name>/
```

- `p2p_share/` is the core: `protocol.py` (newline-delimited JSON over TCP), `chunking.py` and `storage.py` (streaming manifests and the shared library), `peer.py` (threaded server), `client.py` (parallel, resumable, verifying downloader), `tamper.py` (the corrupt-a-chunk switch), `cli.py`.
- `api/` wraps one peer or one client in a small FastAPI app and streams what happens to the browser as server-sent events. The same image runs every role, chosen by the `ROLE` environment variable.
- `web/` is the React app. Its chunk mosaic is driven by the real events, not a timer.

### Peer protocol

Each message is one line of JSON over TCP.

| Request | Response | Purpose |
|---|---|---|
| `GET_CATALOG` | `CATALOG` | List shared files |
| `GET_MANIFEST` | `MANIFEST` | Chunk hashes for one file |
| `GET_CHUNK` | `CHUNK` | One chunk, base64-encoded |
| `REFRESH` | `REFRESHED` | Rescan the shared folder |
| anything invalid | `ERROR` | The connection stays open and usable |

A file's ID is the SHA-256 of its contents. Two files with identical bytes are listed once, with the other name shown as an alias. Lines longer than 4 MiB close the connection, and peers refuse chunk sizes above 2 MiB.

### Integrity

1. Each chunk's SHA-256 is checked as it arrives. A bad chunk is requested again, up to `--retries` times.
2. The whole file's SHA-256 is checked before the `.part` file is renamed into place. A mismatch deletes the partial file.

## Configuration

Environment variables for the API containers (see `docker-compose.yml` for examples):

| Variable | Used by | Meaning | Default |
|---|---|---|---|
| `ROLE` | all | `uploader` or `downloader` | `uploader` |
| `SHARE_DIR` | uploader | Folder to share | `./shared` |
| `PEER_PORT` | uploader | Peer protocol port | `9000` |
| `CHUNK_SIZE` | uploader | Bytes per chunk | `262144` |
| `SEED_SAMPLE`, `SEED_INDEX` | uploader | Create a 2 MB sample file if the folder is empty | off |
| `MAX_UPLOAD_MB` | uploader | Largest accepted upload | `512` |
| `DOWNLOAD_DIR` | downloader | Where finished files go | `./downloads` |
| `PEERS` | downloader | `Label=host:port,Label2=host:port` | none |

## Develop

```bash
pip install -e ".[api,dev]"
python -m pytest -q                      # Python tests

cd web && npm install
npm test                                 # UI tests
npm run build                            # type-check and production build

# With the stack running, check it end to end:
python scripts/smoke.py
```

To work on the UI with hot reload, run the three APIs locally on ports 8001 (uploader), 8002 (uploader 2) and 8003 (downloader), then `npm run dev` in `web/` and open <http://localhost:5173>. For example:

```bash
ROLE=uploader SHARE_DIR=./shared PEER_PORT=9000 uvicorn api.main:app --port 8001
ROLE=downloader DOWNLOAD_DIR=./downloads PEERS="Uploader=127.0.0.1:9000" uvicorn api.main:app --port 8003
```

## Limits worth knowing

- This is a demo on one machine. There is no authentication or encryption, so the compose file publishes every port on 127.0.0.1 only. Change that deliberately, and only for a network you trust.
- Chunks travel base64-encoded inside JSON, which adds about a third to the bytes on the wire.
- Peers don't discover each other. The downloader is given a list of peers, and each download comes from a single peer.
- Downloads started from the web app always get a fresh file name, so resume applies to the CLI (same output path), not to the web app.
- The event history is kept in memory (the last 300 events per container), so restarting a container clears it.

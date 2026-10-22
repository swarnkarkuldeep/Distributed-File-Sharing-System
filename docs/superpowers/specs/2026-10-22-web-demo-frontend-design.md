# Web demo frontend + Docker one-click run — design and implementation plan

Status: DRAFT, awaiting approval. Nothing below has been built yet.

## 1. Intent

The project is a Python P2P file-sharing system (chunked transfer, per-chunk and whole-file SHA-256). It is only usable from a CLI, which makes it a poor demo. The owner will demo it **on one laptop**, with **two browser windows side by side**: an **Uploader** window and a **Downloader** window. The whole thing must start with `docker compose up` (or one click in Docker Desktop).

What the audience should see: a file is dropped in one window, appears in the other, and moves across as visible chunks, each lighting up as its hash is verified; then a final whole-file check.

## 2. Goals / non-goals / anti-goals

Goals
- React + Vite UI with two routes: `/uploader` and `/downloader`, meant to be opened in separate windows.
- Real transfers over the existing TCP protocol (the UI must not fake progress).
- Live chunk-level visualisation on both sides, driven by server events.
- One-click start: `docker compose up` → open `http://localhost:8080`.
- Glassmorphism look, animated, with a Google Font that is not Inter/Roboto/Space Grotesk.
- An optional "tamper a chunk" demo showing corruption being caught and retried.

Non-goals
- Auth, accounts, internet exposure, multi-user hosting.
- Replacing the TCP protocol with HTTP. The CLI keeps working unchanged.
- Peer discovery / DHT.

Anti-goals (would make this a failure even if it "works")
- A UI that animates on a timer instead of real events.
- A demo that finishes in 10 ms so nobody sees anything (see "demo speed" below).
- Needing Node/Python installed on the laptop, or manual steps beyond Docker.

## 3. Architecture

```
Browser window 1  /uploader   ─┐                          ┌─ api (ROLE=uploader)   ── TCP peer :9000 ◄──┐
                               ├─►  web (nginx :8080) ───►│                        shared volume        │ P2P protocol
Browser window 2  /downloader ─┘   serves Vite build,     └─ api (ROLE=downloader) ── P2PClient ────────┘
                                   proxies /api/uploader/*, /api/downloader/*
```

Three containers from two images:
- `web`: multi-stage build (node → nginx). Static React app; reverse-proxies `/api/uploader/` and `/api/downloader/` (including SSE, buffering off).
- `uploader` and `downloader`: same Python image, `ROLE` env var selects behaviour. Python API layer: FastAPI + uvicorn (new dependency; the core `p2p_share` package stays stdlib-only).
  - `uploader`: runs `P2PPeerServer` on 9000 in a thread and the HTTP API on 8000. API: upload file (multipart, streamed to the shared volume), list, remove, tamper toggle, SSE event stream.
  - `downloader`: HTTP API only. API: connect to `host:port` (default `uploader:9000`), list remote catalog, start download, SSE progress stream, list saved files, fetch a saved file to the user's PC.
- Volumes: named volumes `shared` and `downloads` (a bind mount of `./shared` would drag the 1.7 GB `.mkv` into the demo). Port 9000 is also published so the CLI can still be used against the container.

Required changes to existing Python code (small, additive):
- `peer.py`: an event hook (callback) fired on catalog/manifest/chunk requests, plus a tamper option. No protocol change.
- `client.py`: a progress callback per chunk; incremental hashing; write to `*.part` then rename.
- `storage.py` / `chunking.py`: streaming hashing; lock around refresh.

## 4. UI design (frontend-design plan)

Subject: moving a file between two machines in verified pieces. The vernacular is chunks, hashes, handshakes, not "dashboard".

Memorable element (the one place boldness is spent): the **chunk mosaic**. Every chunk is a glass tile. On the uploader a tile pulses when served; on the downloader it flips from frosted to lit when its SHA-256 matches. A tampered chunk turns red, shakes once, then re-fetches and lights. The mosaic is the same component in both windows so the audience reads one story from two angles.

Tokens
- Color: base `#0A1630` (deep navy), aurora blobs `#FF8A70` (coral, the uploader's glow), `#4FE3D0` (aqua, the downloader's glow), `#8F7CFF` (violet, shared), glass fill `rgba(255,255,255,0.08)` with 1px `rgba(255,255,255,0.18)` border and `backdrop-filter: blur(18px) saturate(140%)`, error `#FF5C7A`. The two windows get different dominant glows so they are distinguishable from the back of a room.
- Type: **Bricolage Grotesque** (Google Fonts) for everything, with its width/optical-size axes used for headings; **JetBrains Mono** only for hashes and byte counts, where monospace is functional. Sentence case, no all-caps eyebrows.
- Layout: left-aligned content in a single glass column per window, max ~720 px so two windows fit side by side on a 1080p screen. Hero is the live mosaic, not a headline.
- Motion: one orchestrated moment (the mosaic). Everything else responds to user action (drop, connect, click). `prefers-reduced-motion` turns the mosaic into a plain progress bar. Real focus rings, AA contrast on glass (add a darker scrim behind text).
- Performance guard: `backdrop-filter` is capped to a few large panels, not every tile, so 4,800-chunk files stay smooth. The mosaic aggregates chunks into at most ~400 tiles for big files, and is drawn on `<canvas>`.

Review against defaults: first draft was "dark navy + neon accent + rounded cards", which is the generic glassmorphism template. Changes: the two roles get opposite warm/cool glows instead of one accent; the mosaic replaces the usual stats-row hero; no per-card hover lift on every item.

Copy: action names stay consistent end to end ("Share" → "Shared", "Download" → "Downloading" → "Downloaded and verified"). Errors say what failed and what to do ("Chunk 12 failed its hash check. Retrying from the peer.").

## 5. Implementation plan (ordered)

Phase 0: fix what the frontend would otherwise expose (see section 6, items 1–6).
Phase 1: backend seams: event hooks in `peer.py`, progress callback in `client.py`, streaming hashing, lock, tamper option; add tests (corrupt chunk, bad message, empty file, duplicate content).
Phase 2: `api/` package: FastAPI app with `ROLE` switch, SSE endpoints, upload/stream-to-disk, saved-file download.
Phase 3: `web/` Vite + React + TypeScript app: routes, SSE hook, mosaic canvas, upload dropzone, connect/catalog/download views, tamper toggle, demo-speed slider.
Phase 4: Docker: `Dockerfile.api`, `Dockerfile.web`, `docker-compose.yml` (healthchecks, `depends_on`, named volumes, published 8080 and 9000).
Phase 5: README rewrite (remove claims that are not true), `.gitignore` additions, `docker compose up` smoke test, two-window demo script.

Verification: pytest for Python; Vitest for the SSE/mosaic reducers; a compose smoke test (upload a file via API, download it via the other API, compare hashes); a manual two-window run through the browser.

## 6. Catches found in the existing project

Bugs / risks (priority order)
1. **Whole-file reads.** `chunking.build_manifest` does `path.read_bytes()`, and `SharedLibrary.refresh()` hashes every file at startup. `shared/` holds a 1.7 GB `.mkv`: that is ~1.7 GB of RAM plus a long start, and would likely OOM a container with a memory limit. Fix: hash in a streaming pass.
2. **Client holds the whole download in memory** (`b"".join(chunks)`), and writes the destination only at the end. Fix: incremental write to `*.part`, incremental file hash, rename on success.
3. **Server crashes a handler thread on bad input.** `int(message.get("index", -1))` raises `ValueError` on `"abc"`, and a JSON message that is not an object makes `.get` raise `AttributeError`. Only `ConnectionError/OSError/ProtocolError` are caught, so the thread dies with a traceback and the client sees a dropped connection. Fix: validate and reply with an error message.
4. **Unbounded `readline()`.** A peer can send an endless line without a newline and exhaust memory. Fix: cap message size.
5. **Race in `refresh()`.** It does `self._files.clear()` then repopulates while handler threads read, so a client can see "file not found" mid-refresh. Fix: build a new dict and swap, under a lock.
6. **Catalog goes stale.** Files are scanned once at startup; the only way to pick up new ones is a `REFRESH` message that the CLI cannot send. The web upload path needs to add files and update the catalog atomically.
7. **Same content collapses.** Two files with identical bytes get one `file_id`, so one name silently disappears from the catalog.
8. **`stop()` does not stop the server.** `accept()` blocks forever, so the shutdown event is never checked. Fix: close the socket or use a timeout.
9. **No retry or resume** on a failed chunk, although the README claims "failed chunks can be re-downloaded independently" and "resume/pause".
10. Smaller: `read_in_chunks` is unused; `CHUNK.chunk_hash` is sent but never checked by the client; subdirectories and dotfiles in `shared/` are handled inconsistently (subdirectories skipped, hidden files shared); the manifest reports `file_size` from `stat()` after reading the bytes, so a file changing in between gives inconsistent metadata.

Repo hygiene
- `downloads/output.bin` is committed; `downloads/` should be ignored.
- `.gitignore` lacks `node_modules/`, `dist/`, `.superpowers/`, and large files in `shared/`.
- `steps.txt` duplicates the README quick start; fold it in or delete.
- `.gitkeep` at the root does nothing.
- `README.md` overclaims: parallel chunk downloads, resume/pause, "memory O(chunk_size)", "fault tolerance", "network timeouts prevent hanging operations" (only the client has a timeout, the server has none). It also hardcodes a file ID. Either implement these or soften the text.
- Tests: one happy-path test using `time.sleep(0.25)` to wait for the server (flaky). No tests for corruption, missing file, bad input, empty file, or concurrency.
- Remote branch `origin/codex/add-clean-minimal-gui` exists; check whether it contains anything worth reusing before starting.

## 7. Suggestions beyond what was asked (opt-in)

- **Demo speed slider** (strongly recommended): localhost transfers finish in milliseconds. A per-chunk delay on the downloader makes the mosaic watchable. This is essential, not a nicety.
- **"Tamper a chunk" button** on the uploader: flips a byte in one served chunk, once, so the downloader shows the hash catch and self-heals. This is the best 10 seconds of the demo.
- **Resume** from the `.part` file (cheap once chunks are written incrementally and verified).
- **Parallel chunk fetching** over N connections (makes the README's claim true; the mosaic then fills out of order, which looks great).
- **Second uploader container** (compose profile) so the downloader can pick between two peers, to show "distributed".
- **Save to my PC** button so a downloaded file can leave the container via the browser.

## 8. Decisions made by me (not yet confirmed by the owner)

- FastAPI + SSE, rather than WebSockets or a Node backend.
- Named Docker volumes, rather than bind mounts.
- Bricolage Grotesque + JetBrains Mono, navy base with coral/aqua split glows.
- TypeScript for the React app.
- Port 8080 for the UI, 9000 published for the CLI.

## 9. Owner decisions (2026-10-22)

1. Tamper-a-chunk demo: **included**.
2. Parallel chunk downloads and a second uploader container: **included now**. Resume stays opt-in via `.part` (included since it falls out of the incremental write).
3. All catches in section 6 are **to be fixed**.
4. The 1.7 GB `.mkv` is **out of scope for now**; keep it out of the demo volumes (streaming hashing still gets fixed).

Status: approved to proceed to the task-level plan.

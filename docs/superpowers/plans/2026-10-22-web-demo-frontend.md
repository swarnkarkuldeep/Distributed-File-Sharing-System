# Web demo frontend + Docker one-click run — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the P2P core, add parallel/resumable/tamper-aware transfers, and ship a React + Vite glassmorphism UI (separate Uploader and Downloader windows) that starts with a single `docker compose up`.

**Architecture:** The stdlib-only `p2p_share` package stays the core and keeps its wire protocol. A thin FastAPI layer (`api/`, one image, `ROLE` env var) wraps a peer server (uploader role) or the client (downloader role) and streams real events over SSE. A React SPA served by nginx talks to `/api/<node>/…` (nginx proxies to each container). Compose runs `web`, `uploader`, `uploader2`, `downloader`.

**Tech Stack:** Python 3.10+ (container 3.12), pytest, FastAPI + uvicorn + python-multipart, httpx (tests); Vite + React + TypeScript, react-router-dom, Vitest, `@fontsource-variable/bricolage-grotesque`, `@fontsource-variable/jetbrains-mono`; nginx; Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-22-web-demo-frontend-design.md`

## Global Constraints

- Core package `p2p_share` stays **standard-library only**; new dependencies live only in `api/` (`pip install ".[api]"`) and `web/`.
- Wire protocol request/response type names (`GET_CATALOG/CATALOG`, `GET_MANIFEST/MANIFEST`, `GET_CHUNK/CHUNK`, `REFRESH/REFRESHED`) are unchanged; the only addition is `{"type":"ERROR","ok":false,"error":str}` replies for bad requests. The existing CLI commands keep working.
- Defaults: chunk size 256 KiB in code; **16 KiB in compose** (`CHUNK_SIZE=16384`) so small demo files give 100+ visible chunks. Max accepted chunk size 2 MiB. Max protocol line 4 MiB.
- Ports: UI `8080`; uploader peer `9000` published as `9000:9000`; uploader2 peer published as `9001:9000`; API containers listen on `8000` (not published).
- Volumes: named volumes `shared1`, `shared2`, `downloads`. Never bind-mount `./shared`.
- Download behavior: 4 parallel connections by default, 3 retries per chunk, writes `<name>.part` then atomic rename; whole-file SHA-256 is checked before rename.
- UI copy: sentence case, no all-caps labels, same verb through a flow (Share → Shared; Download → Downloading → Downloaded and verified). Errors say what failed and what to do.
- Fonts: Bricolage Grotesque (all text), JetBrains Mono (hashes and byte counts only), bundled via `@fontsource-variable` so the demo works offline.
- Colors: base `#0A1630`; uploader glow `#FF8A70`; downloader glow `#4FE3D0`; shared accent `#8F7CFF`; error `#FF5C7A`; glass fill `rgba(255,255,255,0.08)`, border `rgba(255,255,255,0.18)`, `backdrop-filter: blur(18px) saturate(140%)`.
- Honor `prefers-reduced-motion` (mosaic becomes a plain progress bar), visible keyboard focus, AA text contrast on glass, usable at 360 px wide.
- Work on branch `feature/web-demo`; one commit per task.

## Event contracts (shared by api/ and web/)

Peer events (uploader bus): `{"type":"peer","seq":int,"ts":float,"kind":"connect|disconnect|catalog|manifest|chunk|refresh|tamper_served","remote":"ip:port","file_id":str|null,"file_name":str|null,"index":int|null,"chunk_count":int|null}`.
File events (uploader bus): `{"type":"file","kind":"added|removed","file":<catalog entry>}`; tamper events: `{"type":"tamper","armed":bool,"file_id":str|null,"index":int|null,"once":bool}`.
Download events (downloader bus): `{"type":"download","download_id":str,"seq":int,"ts":float,"kind":"manifest|resumed|chunk_ok|chunk_failed|verifying|done|error|cancelled","index":int|null,"chunk_count":int,"bytes_done":int,"file_size":int,"file_name":str,"message":str|null}`.
Catalog entry: manifest dict (`file_id,file_name,file_size,chunk_size,chunk_hashes,file_hash,chunk_count`) plus `aliases: list[str]`.

## Review Focus

Each line has its test in the named task.

1. Empty (0-byte) file shared and downloaded → completes, hash of empty input verifies (Tasks 2, 5).
2. Upload with a hostile or odd filename (`../../etc/x`, `.hidden`, unicode, same name twice, same bytes under a new name) → stored safely inside the shared dir, never overwrites, both names visible (Tasks 2, 8).
3. Peer drops or is unreachable mid-download → clear `error` event within the timeout, `.part` kept for resume, no hang (Tasks 5, 9).
4. A malformed request (string index, JSON array, oversized line, idle socket) → error reply or clean close; server keeps serving others (Tasks 1, 4).
5. Browser reconnects its SSE stream after a refresh → replays history, no duplicate chunk tiles (Tasks 7, 10).

---

### Task 0: Branch, hygiene, recon

**Files:**
- Modify: `.gitignore`, `pyproject.toml`
- Delete: `.gitkeep`, `steps.txt` (content moves to README in Task 16); `git rm --cached downloads/output.bin`

- [ ] **Step 1:** `git switch -c feature/web-demo`. Inspect the old remote branch for reusable work: `git ls-tree -r --name-only origin/codex/add-clean-minimal-gui`. Note findings in the commit message only; do not merge it.
- [ ] **Step 2:** `.gitignore` gains `node_modules/`, `dist/`, `.superpowers/`, `downloads/`, `shared/*` with `!shared/test.txt`, `*.part`, `.venv/`, `.pytest_cache/`, `web/coverage/`.
- [ ] **Step 3:** `pyproject.toml`: add `[project.optional-dependencies]` `api = ["fastapi>=0.115", "uvicorn>=0.30", "python-multipart>=0.0.9"]` and `dev = ["pytest>=8", "httpx>=0.27"]`; set `[tool.setuptools] packages = ["p2p_share", "api"]`.
- [ ] **Step 4:** Run `python -m pip install -e ".[api,dev]"` then `python -m pytest -q`. Expected: the existing test passes.
- [ ] **Step 5:** Commit `chore: branch hygiene, optional deps`.

### Task 1: Protocol hardening

**Files:** Modify `p2p_share/protocol.py`; Test `tests/test_protocol.py`

**Interfaces:**
- Produces: `MAX_LINE_BYTES: int = 4 * 1024 * 1024`; `receive_message(sock_file) -> dict[str, Any]` raising `ProtocolError` for EOF, oversized line, invalid JSON, and non-object JSON.

- [ ] **Step 1:** Write failing tests using `io.StringIO`: `test_eof_raises`, `test_invalid_json_raises`, `test_json_array_raises` (`"[1,2]\n"`), `test_oversized_line_raises` (`"x" * (MAX_LINE_BYTES + 10)`, no newline), `test_valid_object_returned`.
- [ ] **Step 2:** `python -m pytest tests/test_protocol.py -v` → FAIL.
- [ ] **Step 3:** Implement with `sock_file.readline(MAX_LINE_BYTES + 1)`; a result longer than `MAX_LINE_BYTES` or lacking a trailing newline at the limit is an error. Also `send_message` stays as is.
- [ ] **Step 4:** Run tests → PASS. Commit `fix: bound protocol line size and reject non-object messages`.

### Task 2: Streaming manifests and a safe SharedLibrary

**Files:** Modify `p2p_share/chunking.py`, `p2p_share/storage.py`; Test `tests/test_storage.py`

**Interfaces:**
- Produces: `build_manifest(path: Path, chunk_size: int = 262144) -> FileManifest` (single streaming pass using `read_in_chunks`; `file_size` is bytes actually read). `SharedFile` gains `aliases: list[str]`. `SharedLibrary` methods: `refresh() -> None` (builds a new dict then swaps under a lock), `add_file(path: Path) -> FileManifest`, `remove_file(file_id: str) -> bool` (also deletes backing files), `catalog() -> list[dict]` (entries include `aliases`), `get_manifest(file_id) -> FileManifest | None`, `get_chunk(file_id, index) -> tuple[bytes, str] | None` (returns `None` if the data read no longer matches the manifest hash). Directories and names starting with `.` are skipped everywhere.

- [ ] **Step 1:** Failing tests: `test_empty_file_manifest` (`chunk_count == 0`, `file_hash == sha256(b"").hexdigest()`); `test_manifest_streams_without_loading_file` (8 MiB file, 64 KiB chunks, `tracemalloc` peak < 1 MiB); `test_duplicate_content_becomes_alias` (two names, one catalog entry, `aliases` holds the second name); `test_hidden_and_directories_ignored`; `test_get_chunk_detects_file_changed_on_disk` (modify file after refresh → `None`); `test_refresh_never_hides_files_from_readers` (reader thread calls `get_manifest(known_id)` 2000 times while another thread calls `refresh()` repeatedly; never `None`); `test_add_and_remove_file`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement as specified; `RLock` guards the dict reference only, swap is one assignment.
- [ ] **Step 4:** Run → PASS. Commit `fix: streaming hashing, atomic refresh, alias handling`.

### Task 3: Tamper control

**Files:** Create `p2p_share/tamper.py`; Test `tests/test_tamper.py`

**Interfaces:**
- Produces: `class TamperControl` with `arm(file_id: str, index: int, once: bool = True) -> None`, `disarm() -> None`, `apply(file_id: str, index: int, data: bytes) -> tuple[bytes, bool]` (flips the first byte via XOR `0xFF`, returns `(data, True)` when armed for that chunk; consumes the arming when `once`), `state() -> dict | None` (`{"file_id","index","once"}`). Thread-safe.

- [ ] **Step 1:** Failing tests: `test_unarmed_returns_data_unchanged`; `test_once_tampers_first_request_only`; `test_persistent_tampers_every_time`; `test_other_chunk_untouched`; `test_disarm`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement with a `threading.Lock`. **Step 4:** Run → PASS. Commit `feat: tamper control for corruption demo`.

### Task 4: Robust peer server with events

**Files:** Modify `p2p_share/peer.py`; Test `tests/test_peer.py`

**Interfaces:**
- Consumes: `SharedLibrary` (Task 2), `TamperControl` (Task 3), `MAX_LINE_BYTES` behavior (Task 1).
- Produces: `P2PPeerServer(share_dir, host="0.0.0.0", port=9000, chunk_size=262144, on_event: Callable[[dict], None] | None = None, idle_timeout_s: float = 120.0)`; raises `ValueError` if `chunk_size` is not in `1..2*1024*1024`. Attributes: `ready: threading.Event` (set once listening), `bound_port: int` (supports `port=0`), `library: SharedLibrary`, `tamper: TamperControl`. `start()` blocks until `stop()`; `stop()` unblocks `accept()` (socket timeout loop or close). Emits peer events per the contract above. Bad requests get `{"type":"ERROR","ok":false,"error":...}` and the connection stays usable.

- [ ] **Step 1:** Failing tests using `port=0` and `server.ready.wait(5)` (no sleeps): `test_string_index_gets_error_reply_and_connection_survives`; `test_json_array_gets_error_reply`; `test_oversized_line_closes_connection_server_keeps_serving`; `test_idle_connection_is_closed` (`idle_timeout_s=0.2`); `test_stop_unblocks_start`; `test_chunk_size_validation`; `test_events_emitted_for_catalog_and_chunk` (collect via `on_event`, assert kinds and `chunk_count`); `test_tampered_chunk_served_with_true_hash` (arm once; first `GET_CHUNK` data hash ≠ `chunk_hash`, second matches; a `tamper_served` event is emitted).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. Wrap handler dispatch so any `ValueError/TypeError/KeyError` becomes an ERROR reply; unexpected exceptions close only that connection and emit `disconnect`.
- [ ] **Step 4:** Update `tests/test_transfer.py` to wait on `server.ready` instead of `time.sleep(0.25)`. Run all → PASS. Commit `fix: validate requests, idle timeout, clean shutdown, event hooks`.

### Task 5: Parallel, resumable, verifying client

**Files:** Modify `p2p_share/client.py`; Test `tests/test_client.py`

**Interfaces:**
- Consumes: peer server (Task 4) and `TamperControl` via `server.tamper`.
- Produces: `IntegrityError`, `DownloadCancelled` exceptions; `@dataclass ProgressEvent(kind: str, chunk_count: int, bytes_done: int, file_size: int, file_name: str, index: int | None = None, message: str | None = None)` with `to_dict()`; `P2PClient(host, port, timeout_s=20.0, connections=4, retries=3, chunk_delay_s=0.0)`; `list_files() -> list[dict]`; `refresh() -> int` (sends `REFRESH`, returns count); `download(file_id: str, destination: Path, on_progress: Callable[[ProgressEvent], None] | None = None, cancel: threading.Event | None = None) -> Path`.
- Behavior: manifest on one connection; N worker threads each with their own socket; each chunk hash-checked and written at its offset into `<destination>.part` (preallocated to `file_size`); on a bad hash emit `chunk_failed` and re-request up to `retries` times; existing `.part` of the right size is re-verified chunk by chunk and valid chunks are skipped (`resumed` event with the count); after all chunks, stream the `.part` through SHA-256 (`verifying`), compare to `file_hash`, `os.replace` to `destination` (`done`). Whole-file mismatch deletes `.part`. Cancel → `DownloadCancelled`, `.part` kept. `chunk_delay_s` sleeps after each chunk. Errors also emit an `error` event before raising.

- [ ] **Step 1:** Failing tests (real server, `port=0`, chunk size 128 or 4096): `test_parallel_download_matches_source` (`connections=4`, multi-chunk file); `test_each_chunk_reported_ok_exactly_once`; `test_empty_file_downloads`; `test_tamper_once_is_caught_and_healed` (a `chunk_failed` then success, file correct); `test_tamper_persistent_fails_after_retries` (raises `IntegrityError`, destination does not exist); `test_resume_skips_valid_chunks` (pre-write the first half into `.part`, assert `resumed` count and that the server saw fewer `chunk` events); `test_cancel_raises_and_keeps_part`; `test_unreachable_peer_raises_oserror_quickly` (`timeout_s=1`); `test_peer_dropping_mid_download_emits_error_and_keeps_part` (server stopped from an `on_progress` hook); `test_chunk_delay_slows_download`; `test_refresh_picks_up_new_file`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement per the behavior above (work queue of indices, `queue.Queue`; file writes via a shared handle with `os.pwrite`-style locking since Windows lacks `pwrite`). **Step 4:** Run → PASS; run the full suite. Commit `feat: parallel resumable verified downloads with progress events`.

### Task 6: CLI

**Files:** Modify `p2p_share/cli.py`; Test `tests/test_cli.py`

**Interfaces:**
- Consumes: `P2PClient` (Task 5). Produces: `parse_peer("host:port")` raising `argparse.ArgumentTypeError` for a missing or non-numeric port; `download` gains `--connections` (default 4), `--retries` (default 3) and prints a single-line progress counter; new `refresh <peer>` subcommand.

- [ ] **Step 1:** Failing tests: `test_parse_peer_rejects_non_numeric_port`, `test_parse_peer_accepts_ipv4_host_port`, `test_cli_download_end_to_end` (real server, call `main()` with patched `sys.argv`, assert file bytes), `test_cli_refresh_prints_count`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. Commit `feat: cli refresh, progress and options`.

### Task 7: API core (settings, event bus, app factory, seed)

**Files:** Create `api/__init__.py`, `api/settings.py`, `api/events.py`, `api/app.py`, `api/seed.py`, `api/sse.py`; Test `tests/test_api_core.py`

**Interfaces:**
- Produces: `Settings.from_env() -> Settings` with fields `role: Literal["uploader","downloader"]`, `share_dir: Path`, `download_dir: Path`, `peer_port: int`, `chunk_size: int`, `peers: list[PeerRef]` (`PeerRef(label: str, host: str, port: int)`, parsed from `PEERS="Uploader=uploader:9000,Uploader 2=uploader2:9000"`), `seed_sample: bool`, `max_upload_mb: int`. `EventBus(history: int = 300)`: `publish(event: dict) -> None` (thread-safe, assigns increasing `seq`, stamps `ts`), `history_since(seq: int) -> list[dict]`, `async stream(last_seq: int = 0) -> AsyncIterator[dict]`. `sse_response(bus: EventBus, request) -> StreamingResponse` (`id: <seq>` and `data: <json>` lines, `: ping` every 15 s, honors `Last-Event-ID`). `create_app(settings: Settings | None = None) -> FastAPI` (builds role router; Tasks 8 and 9 supply `uploader_router(...)`/`downloader_router(...)`). `seed_sample(directory: Path, name: str, size: int, seed: int) -> Path | None` (writes deterministic pseudo-random bytes only when the directory has no visible files).

- [ ] **Step 1:** Failing tests: `test_settings_parse_peers`; `test_bus_assigns_increasing_seq_and_trims_history`; `test_history_since_returns_only_newer`; `test_publish_from_other_thread_reaches_stream` (async test with `pytest.mark.anyio` or `asyncio.run`); `test_seed_is_deterministic_and_skips_nonempty_dir`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. Commit `feat(api): settings, event bus, SSE helper, seed`.

### Task 8: Uploader API

**Files:** Create `api/uploader.py`; Test `tests/test_api_uploader.py` (FastAPI `TestClient`, `ROLE=uploader`, `peer_port=0`)

**Interfaces:**
- Consumes: `P2PPeerServer` (Task 4), `EventBus`/`create_app` (Task 7). Produces `uploader_router(settings, bus) -> APIRouter` mounted at `/`, and starts the peer server in a daemon thread on app startup (stopped on shutdown) with `on_event=lambda e: bus.publish({"type":"peer", **e})`.
- Routes: `GET /status -> {role, peer_port, chunk_size, file_count, tamper}`; `GET /files -> list[catalog entry]`; `POST /files` (multipart field `file`, streamed to `.<uuid>.upload` then renamed; **201** with the catalog entry; **413** over `max_upload_mb`); `DELETE /files/{file_id}` (204/404); `PUT /tamper {file_id, index, once=true}` (404 unknown file, 422 index out of range) and `DELETE /tamper`; `GET /events` (SSE). Filename rule: `Path(name).name`, strip control characters and leading dots, empty → `upload`; collisions become `name (2).ext`. Publishes `file` and `tamper` events.

- [ ] **Step 1:** Failing tests: `test_upload_lists_and_serves_over_tcp` (upload bytes, `P2PClient` downloads them back identical); `test_hostile_filename_stays_inside_share_dir` (`../../evil.txt` and `.hidden`); `test_same_name_twice_gets_suffix`; `test_same_bytes_new_name_becomes_alias`; `test_empty_file_upload`; `test_oversized_upload_413`; `test_delete_file`; `test_tamper_arm_and_disarm_roundtrip`; `test_tamper_unknown_file_404`; `test_events_history_contains_file_added`; `test_seed_sample_shared_on_start` (`seed_sample=True`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. Commit `feat(api): uploader endpoints`.

### Task 9: Downloader API

**Files:** Create `api/downloader.py`; Test `tests/test_api_downloader.py` (real in-process `P2PPeerServer` on `port=0` as the peer)

**Interfaces:**
- Consumes: `P2PClient`/`ProgressEvent` (Task 5), `EventBus`/`Settings` (Task 7). Produces `downloader_router(settings, bus) -> APIRouter`.
- Routes: `GET /status`; `GET /peers -> [{label, host, port, reachable}]` (1 s reachability probe each); `GET /peers/files?peer=<label or host:port> -> catalog` (502 `{error}` when unreachable); `POST /downloads {peer, file_id, connections=4, chunk_delay_ms=0}` → **202** `{download_id}` (runs in a worker thread; each `ProgressEvent` becomes a `download` event with that `download_id`; cancelled/err cases publish `cancelled`/`error`); `DELETE /downloads/{download_id}` (sets the cancel event; 202/404); `GET /saved -> [{name, size}]`; `GET /saved/{name}` (file response; 404 for unknown or traversal attempts); `DELETE /saved/{name}`; `GET /events` (SSE). Destination name comes from the catalog entry; collisions become `name (2).ext`.

- [ ] **Step 1:** Failing tests: `test_download_flow_publishes_ordered_events_and_saves_file`; `test_two_downloads_run_concurrently`; `test_cancel_publishes_cancelled`; `test_unreachable_peer_publishes_error_within_timeout`; `test_peers_reports_reachable_flag`; `test_saved_rejects_path_traversal` (`..%2f..%2fetc`); `test_chunk_delay_applied`; `test_tampered_chunk_shows_chunk_failed_then_done`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run the whole Python suite → PASS. Commit `feat(api): downloader endpoints`.

### Task 10: Web scaffold and pure logic

**Files:** Create under `web/`: `package.json`, `vite.config.ts` (dev proxy `/api/<node>/` → `http://localhost:8000..` per node), `tsconfig.json`, `index.html`, `src/main.tsx`, `src/lib/api.ts`, `src/lib/useEventStream.ts`, `src/lib/mosaic.ts`, `src/lib/reducers.ts`, `src/lib/format.ts`; Test `src/lib/*.test.ts`

**Interfaces:**
- Produces: `bucketStates(states: Uint8Array, maxTiles: number): Uint8Array` (chunk states `0 pending, 1 active, 2 verified, 3 failed`; a tile is 3 if any member is 3, else 2 only if all are 2, else 1 if any member is 1 or 2, else 0). `downloadReducer(state: DownloadState, event: DownloadEvent): DownloadState` and `servingReducer(state: ServingState, event: PeerEvent): ServingState` (pure; track per-chunk states, counters, last failure, log lines). `describePeerEvent(e: PeerEvent): string` (e.g. `Served chunk 12 of 48 · report.pdf`). `formatBytes(n: number): string`. `useEventStream<T>(url: string, onEvent: (e: T) => void): "connecting" | "open" | "reconnecting"` (EventSource, resumes from the last `seq`, de-duplicates by `seq`). `api.ts` exposes typed `uploaderApi(node)` and `downloaderApi()` clients for the routes in Tasks 8–9.

- [ ] **Step 1:** `npm create vite@latest web -- --template react-ts`, then `npm i react-router-dom @fontsource-variable/bricolage-grotesque @fontsource-variable/jetbrains-mono` and `npm i -D vitest`. Add `"test": "vitest run"`.
- [ ] **Step 2:** Failing tests: `bucketStates` (tile priority rules, `maxTiles` larger than chunk count returns identity, empty array); `downloadReducer` (`manifest` sizes the array, `chunk_ok` marks verified and bumps `bytesDone`, `chunk_failed` marks 3 then a later `chunk_ok` for the same index returns it to 2, duplicate `seq` ignored, `done` sets status); `servingReducer`; `describePeerEvent`; `formatBytes(0)`, `formatBytes(1536)`.
- [ ] **Step 3:** Run `npm test` → FAIL. **Step 4:** Implement. **Step 5:** Run → PASS. Commit `feat(web): scaffold, api client, pure reducers`.

### Task 11: Glass design system and Mosaic

**Files:** Create `web/src/styles/tokens.css`, `web/src/styles/glass.css`, `web/src/components/Glass.tsx`, `Aurora.tsx`, `Mosaic.tsx`, `ProgressBar.tsx`; Test `src/components/Mosaic.test.tsx` (Vitest + jsdom + Testing Library)

**Interfaces:**
- Produces: `<Glass as? className? tone?: "uploader"|"downloader">` panel; `<Aurora tone>` animated blurred background blobs (transform-only animation); `<Mosaic states: Uint8Array label: string maxTiles?: number = 400 />` drawing bucketed tiles on `<canvas>` (pending frosted, active pulse, verified lit in the window's glow color, failed `#FF5C7A` with a single short shake); under `prefers-reduced-motion` renders `<ProgressBar value max>` instead. The canvas has `role="img"` and an `aria-label` summarizing verified/total.

- [ ] **Step 1:** Failing tests: Mosaic renders a canvas with an aria-label like `32 of 48 chunks verified`; with `matchMedia("(prefers-reduced-motion: reduce)")` mocked true it renders a progressbar element instead.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement tokens (colors from Global Constraints, type scale, spacing), glass utility class, focus ring, components. `backdrop-filter` only on `Glass` panels, not on tiles. **Step 4:** Run → PASS. Commit `feat(web): glass design system and chunk mosaic`.

### Task 12: Uploader page

**Files:** Create `web/src/pages/Uploader.tsx`, `src/components/Dropzone.tsx`, `FileList.tsx`, `ActivityLog.tsx`, `TamperPanel.tsx`; Test `src/pages/Uploader.test.tsx`

**Interfaces:**
- Consumes: `uploaderApi(node)`, `useEventStream`, `servingReducer`, `Mosaic`, `Glass` (Tasks 10–11). Produces `<Uploader node="uploader" | "uploader2" />`, routed at `/uploader` and `/uploader2`.
- Behavior: header shows peer status (port, files shared, stream state) with the coral glow; Dropzone uploads with per-file progress and an error line that names the file; file list with a Remove action; selecting a file shows its served-chunk Mosaic (`servingReducer`); ActivityLog shows `describePeerEvent` lines (newest first, capped at 200); TamperPanel: pick file + chunk index (default: a middle chunk) → button `Corrupt this chunk once` / `Corrupt every time`, shows armed state, `Stop corrupting`. Empty state: “Drop a file here to start sharing it.”

- [ ] **Step 1:** Failing tests with mocked `fetch`/`EventSource`: shows empty-state copy; dropping a file POSTs to `/api/uploader/files`; a `peer` chunk event lights the right tile count in the aria-label; arming tamper PUTs the right body; upload failure shows an error naming the file.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. Commit `feat(web): uploader window`.

### Task 13: Downloader page

**Files:** Create `web/src/pages/Downloader.tsx`, `src/components/PeerPicker.tsx`, `RemoteFiles.tsx`, `TransferCard.tsx`, `SpeedControl.tsx`, `SavedFiles.tsx`; Test `src/pages/Downloader.test.tsx`

**Interfaces:**
- Consumes: `downloaderApi()`, `downloadReducer`, `Mosaic` (Tasks 10–11). Produces `<Downloader />` routed at `/downloader`.
- Behavior: PeerPicker lists configured peers with a reachability dot plus a free-text `host:port` field and `Connect`; RemoteFiles lists the peer's catalog with `Download`; SpeedControl is a slider “Demo speed” (Instant … Slow = 0–200 ms per chunk) and a connections stepper (1–8); each running download renders a TransferCard with the Mosaic, counters (verified, failed, speed), a `Cancel` button, a `Verifying whole file…` state, and the final `Downloaded and verified` line with the file hash in the mono font; SavedFiles lists saved files with `Save to this computer` (link to `/api/downloader/saved/<name>`) and `Delete`. Errors name the peer and what to try (“Can't reach Uploader 2 at uploader2:9000. Check that its container is running.”).

- [ ] **Step 1:** Failing tests with mocked API/SSE: selecting a peer loads its files; Download POSTs the chosen connections and delay; a `chunk_failed` event shows the failure counter then a later `chunk_ok` clears the red tile; `done` shows the verified line; unreachable peer shows the error copy.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS. Commit `feat(web): downloader window`.

### Task 14: Home, routing, two-window launcher

**Files:** Create `web/src/pages/Home.tsx`, `web/src/App.tsx`; Test `src/App.test.tsx`

**Interfaces:**
- Produces: routes `/` (Home), `/uploader`, `/uploader2`, `/downloader`, otherwise a not-found view. Home has two large actions that call `window.open("/uploader", "p2p-uploader", "popup,width=720,height=900")` and the same for the downloader, plus a plain-link fallback, and a one-line note on how to tile the windows.

- [ ] **Step 1:** Failing tests: each route renders its page; unknown route shows not-found; clicking an action calls `window.open` with the right URL. **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run `npm test` and `npm run build` → PASS. Commit `feat(web): routing and launcher`.

### Task 15: Docker, compose, smoke test

**Files:** Create `Dockerfile.api`, `web/Dockerfile`, `web/nginx.conf`, `docker-compose.yml`, `.dockerignore`, `scripts/smoke.py`

**Interfaces:**
- Compose services: `uploader` (`ROLE=uploader`, `PEER_PORT=9000`, `CHUNK_SIZE=16384`, `SEED_SAMPLE=1`, volume `shared1:/data/shared`, ports `9000:9000`), `uploader2` (same with volume `shared2`, ports `9001:9000`, different seed), `downloader` (`ROLE=downloader`, `PEERS="Uploader=uploader:9000,Uploader 2=uploader2:9000"`, volume `downloads:/data/downloads`), `web` (port `8080:80`). API containers have a healthcheck hitting `/status`; `web` `depends_on` them with `condition: service_healthy`. nginx: `location /api/uploader/`, `/api/uploader2/`, `/api/downloader/` proxy to `:8000` with `proxy_buffering off`, `proxy_read_timeout 1h`, `client_max_body_size 600m`; SPA fallback `try_files $uri /index.html`. Compose `name: p2p-share`.
- `scripts/smoke.py` (stdlib only): waits for `GET /api/downloader/status`, uploads a generated 1 MiB file via `/api/uploader/files`, downloads it from the downloader to completion (polls `/api/downloader/saved`), fetches it back and compares SHA-256; then arms a tamper-once on chunk 3, downloads again and asserts the event stream contained a `chunk_failed` followed by `done`. Exits non-zero on any failure.

- [ ] **Step 1:** Write the files. **Step 2:** `docker compose up -d --build` → all four services healthy (`docker compose ps`). **Step 3:** `python scripts/smoke.py` → prints `OK` and exits 0. **Step 4:** `docker compose down -v`. Commit `feat: docker compose one-click run and smoke test`.

### Task 16: README, demo script, final verification

**Files:** Modify `README.md`; Create `docs/DEMO.md`

- [ ] **Step 1:** Rewrite `README.md`: what it is; `docker compose up` → open `http://localhost:8080`; CLI usage (from the deleted `steps.txt`); architecture diagram; protocol table (including the ERROR reply); test commands. Remove or correct every claim the code does not back (parallel downloads and resume are now real; state the memory behavior honestly, including that the API buffers nothing in memory but base64 inflates chunks by 33%).
- [ ] **Step 2:** `docs/DEMO.md`: a 5-minute script (open both windows, drop a file, watch the mosaic, corrupt a chunk, switch to Uploader 2, show Demo speed).
- [ ] **Step 3 (verification):** `python -m pytest -q` green; `cd web && npm test && npm run build` green; `docker compose up --build`, `python scripts/smoke.py` OK. Then drive the UI in a real browser (Claude-in-Chrome): screenshot both windows at 1920×1080 side by side and at 360 px wide; confirm the mosaic fills with real events, the tamper tile turns red then lights, reduced-motion falls back to the progress bar. Fix anything off before reporting.
- [ ] **Step 4:** Commit `docs: readme and demo script`.

---

## Self-review notes

- Spec coverage: architecture (Tasks 7–9, 15), UI design (11–14), catches 1–10 (Tasks 1, 2, 4, 5, 6, 0, 16), tamper (3, 4, 8, 12), parallel/resume (5, 13), second uploader (15, 14), hygiene (0), README honesty (16).
- The 1.7 GB `.mkv` stays out: the volumes are named and `shared/*` is gitignored; streaming hashing (Task 2) makes it safe to add later.
- Types checked across tasks: `ProgressEvent` fields ↔ download event contract; `TamperControl.state()` ↔ tamper event; `PeerRef`/`PEERS` format used in Tasks 7, 9, 15.

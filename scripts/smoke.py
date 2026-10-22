"""End-to-end check against a running `docker compose up`. Standard library only.

    python scripts/smoke.py [base_url]        (default http://localhost:8080)

Uploads a file through the uploader API, downloads it through the downloader API over the
real TCP protocol, compares hashes, then repeats with one chunk corrupted on purpose and
checks that the corruption was caught and healed. Exits non-zero on any failure.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")


def call(method: str, path: str, body: dict | None = None, raw: bytes | None = None, headers: dict | None = None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hdrs = dict(headers or {})
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read()
            return resp.status, payload
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def get_json(path: str):
    status, payload = call("GET", path)
    assert status == 200, f"GET {path} -> {status} {payload[:200]!r}"
    return json.loads(payload)


def upload(name: str, data: bytes) -> dict:
    boundary = uuid.uuid4().hex
    head = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    body = head.encode() + data + f"\r\n--{boundary}--\r\n".encode()
    status, payload = call("POST", "/api/uploader/files", raw=body,
                           headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert status == 201, f"upload -> {status} {payload[:200]!r}"
    return json.loads(payload)


def wait_until(label: str, check, timeout: float = 60.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = check()
            if last:
                return last
        except Exception as exc:  # services may still be starting
            last = exc
        time.sleep(0.5)
    raise AssertionError(f"timed out waiting for {label} (last: {last!r})")


def read_download_events(download_id: str, timeout: float = 30.0) -> list[dict]:
    """Read the downloader's event stream (it replays history) until this download finishes."""
    events: list[dict] = []
    req = urllib.request.Request(BASE + "/api/downloader/events")
    deadline = time.time() + timeout
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            if time.time() > deadline:
                break
            line = line.decode().strip()
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            if event.get("download_id") != download_id:
                continue
            events.append(event)
            if event["kind"] in ("done", "error", "cancelled"):
                break
    return events


def download(file_id: str, peer: str = "Uploader") -> str:
    status, payload = call("POST", "/api/downloader/downloads",
                           {"peer": peer, "file_id": file_id, "connections": 4, "chunk_delay_ms": 0})
    assert status == 202, f"start download -> {status} {payload[:200]!r}"
    return json.loads(payload)["download_id"]


def main() -> None:
    print(f"Smoke test against {BASE}")
    wait_until("downloader", lambda: get_json("/api/downloader/health")["ok"])
    wait_until("uploader", lambda: get_json("/api/uploader/health")["ok"])
    wait_until("uploader 2", lambda: get_json("/api/uploader2/health")["ok"])

    peers = {p["label"]: p for p in get_json("/api/downloader/peers")}
    assert peers["Uploader"]["reachable"] and peers["Uploader 2"]["reachable"], peers
    print("  both peers reachable")

    second = get_json("/api/downloader/peers/files?peer=" + urllib.parse.quote("Uploader 2"))
    assert any(f["file_name"] == "demo-sample-2.bin" for f in second), second
    print("  uploader 2 shares its seeded sample")

    name = f"smoke-{uuid.uuid4().hex[:6]}.bin"
    data = os.urandom(1024 * 1024)
    want = hashlib.sha256(data).hexdigest()
    entry = upload(name, data)
    assert entry["chunk_count"] == 64 and entry["file_id"] == want, entry
    print(f"  uploaded {name} ({entry['chunk_count']} chunks)")

    did = download(entry["file_id"])
    saved = wait_until("download", lambda: next((f for f in get_json("/api/downloader/saved") if f["name"] == name), None))
    status, got = call("GET", "/api/downloader/saved/" + urllib.parse.quote(name))
    assert status == 200 and hashlib.sha256(got).hexdigest() == want and saved["size"] == len(data)
    print("  downloaded and hashes match")

    status, _ = call("PUT", "/api/uploader/tamper", {"file_id": entry["file_id"], "index": 3, "once": True})
    assert status == 200
    did = download(entry["file_id"])
    events = read_download_events(did)
    kinds = [e["kind"] for e in events]
    assert "chunk_failed" in kinds and kinds[-1] == "done", kinds
    failed = next(e for e in events if e["kind"] == "chunk_failed")
    assert failed["index"] == 3, failed
    healed = f"{name[:-4]} (2).bin"
    status, got = call("GET", "/api/downloader/saved/" + urllib.parse.quote(healed))
    assert status == 200 and hashlib.sha256(got).hexdigest() == want
    print("  corrupted chunk 3 was caught, re-fetched, and the file still matches")

    for saved_name in (name, healed):
        call("DELETE", "/api/downloader/saved/" + urllib.parse.quote(saved_name))
    call("DELETE", f"/api/uploader/files/{entry['file_id']}")
    print("OK")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FAILED: {exc}")
        sys.exit(1)

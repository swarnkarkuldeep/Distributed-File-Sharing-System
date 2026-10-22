from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from p2p_share.client import P2PClient, ProgressEvent

from .events import EventBus
from .files import safe_filename, unique_path
from .settings import Settings
from .sse import sse_response

LOOKUP_TIMEOUT_S = 3.0


class DownloadBody(BaseModel):
    peer: str
    file_id: str
    connections: int = Field(default=4, ge=1, le=8)
    chunk_delay_ms: int = Field(default=0, ge=0, le=2000)


def mount_downloader(app: FastAPI, settings: Settings, bus: EventBus) -> None:
    cancels: dict[str, threading.Event] = {}
    cancels_lock = threading.Lock()
    reserved: set = set()

    app.state.on_start.append(lambda: settings.download_dir.mkdir(parents=True, exist_ok=True))

    def resolve_peer(value: str) -> tuple[str, int]:
        for ref in settings.peers:
            if ref.label == value:
                return ref.host, ref.port
        host, _, port = value.strip().rpartition(":")
        if not host or not port.isdigit():
            raise HTTPException(422, "Peer must be a configured name or host:port")
        return host, int(port)

    def catalog_of(peer: str) -> list[dict]:
        host, port = resolve_peer(peer)
        try:
            return P2PClient(host, port, timeout_s=LOOKUP_TIMEOUT_S).list_files()
        except Exception as exc:
            raise HTTPException(502, f"Can't reach {host}:{port}. Check that the peer is running. ({exc})") from exc

    def saved_path(name: str):
        root = settings.download_dir.resolve()
        path = (root / name).resolve()
        if path.parent != root or not path.is_file() or name.startswith(".") or name.endswith(".part"):
            raise HTTPException(404, "No saved file with that name")
        return path

    @app.get("/status")
    def status() -> dict:
        return {"role": "downloader", "peers": [p.label for p in settings.peers]}

    @app.get("/peers")
    def peers() -> list[dict]:
        def probe(ref) -> dict:
            try:
                count = len(P2PClient(ref.host, ref.port, timeout_s=1.0).list_files())
                return {"label": ref.label, "host": ref.host, "port": ref.port, "reachable": True, "file_count": count}
            except Exception:
                return {"label": ref.label, "host": ref.host, "port": ref.port, "reachable": False, "file_count": 0}

        with ThreadPoolExecutor(max_workers=max(1, len(settings.peers))) as pool:
            return list(pool.map(probe, settings.peers))

    @app.get("/peers/files")
    def peer_files(peer: str) -> list[dict]:
        return catalog_of(peer)

    @app.post("/downloads", status_code=202)
    def start_download(body: DownloadBody) -> dict:
        entry = next((e for e in catalog_of(body.peer) if e["file_id"] == body.file_id), None)
        if entry is None:
            raise HTTPException(404, "That peer is not sharing this file any more. Refresh its list.")
        host, port = resolve_peer(body.peer)
        download_id = uuid.uuid4().hex[:8]
        cancel = threading.Event()
        with cancels_lock:
            destination = unique_path(settings.download_dir, safe_filename(entry["file_name"]), reserved)
            reserved.add(destination)
            cancels[download_id] = cancel

        client = P2PClient(host, port, connections=body.connections, chunk_delay_s=body.chunk_delay_ms / 1000)

        def publish(event: ProgressEvent) -> None:
            bus.publish({"type": "download", "download_id": download_id, **event.to_dict()})

        def run() -> None:
            try:
                client.download(body.file_id, destination, on_progress=publish, cancel=cancel)
            except Exception:
                pass  # the client already published an error or cancelled event
            finally:
                with cancels_lock:
                    cancels.pop(download_id, None)
                    reserved.discard(destination)

        threading.Thread(target=run, daemon=True, name=f"download-{download_id}").start()
        return {"download_id": download_id, "file_name": destination.name}

    @app.delete("/downloads/{download_id}", status_code=202)
    def cancel_download(download_id: str) -> dict:
        with cancels_lock:
            cancel = cancels.get(download_id)
        if cancel is None:
            raise HTTPException(404, "That download is not running")
        cancel.set()
        return {"download_id": download_id, "cancelling": True}

    @app.get("/saved")
    def saved() -> list[dict]:
        return [
            {"name": p.name, "size": p.stat().st_size}
            for p in sorted(settings.download_dir.iterdir())
            if p.is_file() and not p.name.startswith(".") and not p.name.endswith(".part")
        ]

    @app.get("/saved/{name}")
    def saved_file(name: str) -> FileResponse:
        path = saved_path(name)
        return FileResponse(path, filename=path.name)

    @app.delete("/saved/{name}", status_code=204)
    def delete_saved(name: str) -> Response:
        saved_path(name).unlink()
        return Response(status_code=204)

    @app.get("/events")
    def events(request: Request):
        return sse_response(bus, request)

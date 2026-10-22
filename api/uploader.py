from __future__ import annotations

import threading
import uuid

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from p2p_share.peer import P2PPeerServer

from .events import EventBus
from .files import safe_filename, unique_path
from .seed import seed_sample
from .settings import Settings
from .sse import sse_response

SAMPLE_BYTES = 2 * 1024 * 1024


class TamperBody(BaseModel):
    file_id: str
    index: int
    once: bool = True


def mount_uploader(app: FastAPI, settings: Settings, bus: EventBus) -> None:
    def on_peer_event(event: dict) -> None:
        bus.publish(event)
        if event["kind"] == "tamper_served" and server.tamper.state() is None:
            bus.publish({"type": "tamper", "armed": False, "file_id": None, "index": None, "once": True})

    server = P2PPeerServer(
        settings.share_dir,
        host="0.0.0.0",
        port=settings.peer_port,
        chunk_size=settings.chunk_size,
        on_event=on_peer_event,
    )
    app.state.peer = server

    def start_peer() -> None:
        settings.share_dir.mkdir(parents=True, exist_ok=True)
        if settings.seed_sample:
            seed_sample(settings.share_dir, f"demo-sample-{settings.seed_index}.bin", SAMPLE_BYTES, settings.seed_index)
        threading.Thread(target=server.start, daemon=True, name="peer-server").start()
        if not server.ready.wait(60):
            raise RuntimeError("peer server did not start")

    app.state.on_start.append(start_peer)
    app.state.on_stop.append(server.stop)

    def entry_for(file_id: str) -> dict | None:
        return next((e for e in server.library.catalog() if e["file_id"] == file_id), None)

    @app.get("/status")
    def status() -> dict:
        return {
            "role": "uploader",
            "peer_port": server.bound_port,
            "chunk_size": settings.chunk_size,
            "file_count": len(server.library.catalog()),
            "tamper": server.tamper.state(),
        }

    @app.get("/files")
    def list_files() -> list[dict]:
        return server.library.catalog()

    @app.post("/files", status_code=201)
    def upload_file(file: UploadFile) -> dict:
        limit = settings.max_upload_mb * 1024 * 1024
        tmp = settings.share_dir / f".{uuid.uuid4().hex}.upload"
        written = 0
        try:
            with tmp.open("wb") as out:
                while block := file.file.read(1024 * 1024):
                    written += len(block)
                    if written > limit:
                        raise HTTPException(413, f"{file.filename or 'File'} is larger than {settings.max_upload_mb} MB")
                    out.write(block)
            target = unique_path(settings.share_dir, safe_filename(file.filename or ""))
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)
        manifest = server.library.add_file(target)
        entry = entry_for(manifest.file_id)
        bus.publish({"type": "file", "kind": "added", "file": entry})
        return entry

    @app.delete("/files/{file_id}", status_code=204)
    def delete_file(file_id: str) -> Response:
        entry = entry_for(file_id)
        if entry is None or not server.library.remove_file(file_id):
            raise HTTPException(404, "That file is not being shared")
        bus.publish({"type": "file", "kind": "removed", "file": entry})
        return Response(status_code=204)

    @app.put("/tamper")
    def arm_tamper(body: TamperBody) -> dict:
        entry = entry_for(body.file_id)
        if entry is None:
            raise HTTPException(404, "That file is not being shared")
        if not 0 <= body.index < entry["chunk_count"]:
            raise HTTPException(422, f"Chunk index must be between 0 and {entry['chunk_count'] - 1}")
        server.tamper.arm(body.file_id, body.index, body.once)
        bus.publish({"type": "tamper", "armed": True, "file_id": body.file_id, "index": body.index, "once": body.once})
        return server.tamper.state()

    @app.delete("/tamper")
    def disarm_tamper() -> dict:
        server.tamper.disarm()
        bus.publish({"type": "tamper", "armed": False, "file_id": None, "index": None, "once": True})
        return {"armed": False}

    @app.get("/events")
    def events(request: Request):
        return sse_response(bus, request)

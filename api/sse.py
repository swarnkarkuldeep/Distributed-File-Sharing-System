from __future__ import annotations

import json

from fastapi import Request
from fastapi.responses import StreamingResponse

from .events import EventBus


def sse_response(bus: EventBus, request: Request, heartbeat_s: float = 15.0) -> StreamingResponse:
    header = request.headers.get("last-event-id", "")
    last_seq = int(header) if header.isdigit() else 0

    async def body():
        async for event in bus.stream(last_seq, heartbeat_s=heartbeat_s):
            if event is None:
                if await request.is_disconnected():
                    return
                yield ": ping\n\n"
                continue
            yield f"id: {event['seq']}\ndata: {json.dumps(event)}\n\n"

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI

from .events import EventBus
from .settings import Settings


def create_app(settings: Settings | None = None, bus: EventBus | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    bus = bus or EventBus()
    on_start: list[Callable[[], None]] = []
    on_stop: list[Callable[[], None]] = []

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        for hook in on_start:
            hook()
        try:
            yield
        finally:
            for hook in on_stop:
                hook()

    app = FastAPI(title=f"p2p-share {settings.role}", lifespan=lifespan)
    app.state.settings = settings
    app.state.bus = bus
    app.state.on_start = on_start
    app.state.on_stop = on_stop

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "role": settings.role}

    if settings.role == "uploader":
        from .uploader import mount_uploader

        mount_uploader(app, settings, bus)
    else:
        from .downloader import mount_downloader

        mount_downloader(app, settings, bus)
    return app

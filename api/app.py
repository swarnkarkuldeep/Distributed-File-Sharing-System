from __future__ import annotations

from fastapi import FastAPI

from .events import EventBus
from .settings import Settings


def create_app(settings: Settings | None = None, bus: EventBus | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    bus = bus or EventBus()
    app = FastAPI(title=f"p2p-share {settings.role}")
    app.state.settings = settings
    app.state.bus = bus

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

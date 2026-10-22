"""ASGI entry point: `uvicorn api.main:app`. Configuration comes from environment variables (see api/settings.py)."""

from .app import create_app

app = create_app()

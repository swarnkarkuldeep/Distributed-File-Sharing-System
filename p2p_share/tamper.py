from __future__ import annotations

import threading


class TamperControl:
    """Optionally corrupts one served chunk so integrity checks can be demonstrated."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._armed: dict | None = None

    def arm(self, file_id: str, index: int, once: bool = True) -> None:
        with self._lock:
            self._armed = {"file_id": file_id, "index": index, "once": once}

    def disarm(self) -> None:
        with self._lock:
            self._armed = None

    def state(self) -> dict | None:
        with self._lock:
            return dict(self._armed) if self._armed else None

    def apply(self, file_id: str, index: int, data: bytes) -> tuple[bytes, bool]:
        with self._lock:
            armed = self._armed
            if not armed or armed["file_id"] != file_id or armed["index"] != index or not data:
                return data, False
            if armed["once"]:
                self._armed = None
        return bytes([data[0] ^ 0xFF]) + data[1:], True

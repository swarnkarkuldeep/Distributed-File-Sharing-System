from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import AsyncIterator


class EventBus:
    """Thread-safe publish, async subscribe, with a replay buffer for reconnecting clients."""

    def __init__(self, history: int = 300) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._history: deque[dict] = deque(maxlen=history)
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []

    def publish(self, event: dict) -> None:
        with self._lock:
            self._seq += 1
            stamped = {**event, "seq": self._seq, "ts": event.get("ts", time.time())}
            self._history.append(stamped)
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, stamped)
            except RuntimeError:
                pass

    def history_since(self, seq: int) -> list[dict]:
        with self._lock:
            return [e for e in self._history if e["seq"] > seq]

    async def stream(self, last_seq: int = 0, heartbeat_s: float | None = None) -> AsyncIterator[dict | None]:
        """Yield events after last_seq. With heartbeat_s, yields None whenever that long passes quietly."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            backlog = [e for e in self._history if e["seq"] > last_seq]
            entry = (loop, queue)
            self._subscribers.append(entry)
        try:
            latest = last_seq
            for event in backlog:
                latest = event["seq"]
                yield event
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), heartbeat_s)
                except asyncio.TimeoutError:
                    yield None
                    continue
                if event["seq"] > latest:
                    latest = event["seq"]
                    yield event
        finally:
            with self._lock:
                if entry in self._subscribers:
                    self._subscribers.remove(entry)

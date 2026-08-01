"""Barramento de eventos para progresso em tempo real (pub/sub)."""
from __future__ import annotations

import asyncio
import json
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, scope: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.setdefault(scope, []).append(q)
        return q

    def unsubscribe(self, scope: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(scope, [])
        if q in subs:
            subs.remove(q)

    def publish(self, scope: str, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(scope, [])):
            try:
                q.put_nowait({"scope": scope, **event})
            except asyncio.QueueFull:
                pass


bus = EventBus()

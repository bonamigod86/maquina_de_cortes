"""Fila de processamento em segundo plano (múltiplos vídeos)."""
from __future__ import annotations

import threading
from collections import deque

from app.core.events import bus


class ProcessingQueue:
    """Fila FIFO com um worker único — processamento pesado fora da thread da API."""

    def __init__(self) -> None:
        self._queue: deque[str] = deque()
        # RLock: enqueue chama snapshot() (e bus.publish) com o lock já segurado
        self._lock = threading.RLock()
        self._current: str | None = None
        self._cancel_events: dict[str, threading.Event] = {}
        self._worker: threading.Thread | None = None
        self._runner_factory = None

    def configure(self, runner_factory) -> None:
        self._runner_factory = runner_factory

    def enqueue(self, project_id: str) -> bool:
        with self._lock:
            if project_id in self._queue or project_id == self._current:
                return False
            self._queue.append(project_id)
            bus.publish("queue", {"type": "queue_update", "queue": self.snapshot()})
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run_loop, daemon=True)
                self._worker.start()
            return True

    def cancel(self, project_id: str) -> None:
        with self._lock:
            ev = self._cancel_events.get(project_id)
            if ev:
                ev.set()

    def _run_loop(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._current = None
                    self._worker = None
                    bus.publish("queue", {"type": "queue_update", "queue": self.snapshot()})
                    return
                pid = self._queue.popleft()
                self._current = pid
                ev = threading.Event()
                self._cancel_events[pid] = ev
            bus.publish("queue", {"type": "queue_update", "queue": self.snapshot()})
            runner = self._runner_factory() if self._runner_factory else None
            if runner:
                try:
                    runner.run(pid, ev)
                except Exception:
                    import traceback

                    traceback.print_exc()
            with self._lock:
                self._cancel_events.pop(pid, None)
                self._current = None

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "current": self._current,
                "pending": list(self._queue),
            }


queue = ProcessingQueue()

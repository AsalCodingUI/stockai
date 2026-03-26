"""Realtime signal pipeline with async queue and persistent store."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SIGNALS_FILE = Path.home() / ".stockai" / "signals.jsonl"
MAX_RECENT = 1000


class RealtimeSignalPipeline:
    """Asynchronous pipeline for signal events and feedback."""

    def __init__(self, max_queue: int = 2000):
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue)
        self._task: asyncio.Task | None = None
        self._running = False
        self._recent: list[dict[str, Any]] = []
        self._total_published = 0
        self._total_written = 0
        self._dropped = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("RealtimeSignalPipeline started")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("RealtimeSignalPipeline stopped")

    async def _run(self) -> None:
        SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        while self._running:
            event = await self._queue.get()
            try:
                self._append_recent(event)
                with SIGNALS_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                self._total_written += 1
            except Exception as exc:
                logger.warning("Realtime pipeline write failed: %s", exc)
            finally:
                self._queue.task_done()

    def _append_recent(self, event: dict[str, Any]) -> None:
        self._recent.append(event)
        if len(self._recent) > MAX_RECENT:
            self._recent = self._recent[-MAX_RECENT:]

    def publish(self, event: dict[str, Any]) -> bool:
        payload = dict(event)
        payload.setdefault("event_time", datetime.now().isoformat())
        try:
            self._queue.put_nowait(payload)
            self._total_published += 1
            return True
        except asyncio.QueueFull:
            self._dropped += 1
            return False

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._recent[-max(1, min(limit, MAX_RECENT)):]

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "total_published": self._total_published,
            "total_written": self._total_written,
            "dropped": self._dropped,
            "signals_file": str(SIGNALS_FILE),
        }


_pipeline: RealtimeSignalPipeline | None = None


def get_realtime_pipeline() -> RealtimeSignalPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RealtimeSignalPipeline()
    return _pipeline


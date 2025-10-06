"""Task queue worker entry points for ADE background jobs."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.lifecycles import ensure_runtime_dirs
from app.services.task_queue import TaskMessage, TaskQueue

TaskProcessor = Callable[[TaskMessage], Awaitable[None]]

_LOGGER = logging.getLogger(__name__)


class JobWorker:
    """Dispatch queued task messages to registered handlers."""

    def __init__(self, queue: TaskQueue) -> None:
        self._queue = queue
        self._handlers: dict[str, TaskProcessor] = {}
        self._subscriber = self._handle_message

    def register(self, name: str, handler: TaskProcessor) -> None:
        """Register ``handler`` for future task messages named ``name``."""

        self._handlers[name] = handler

    async def _handle_message(self, message: TaskMessage) -> None:
        handler = self._handlers.get(message.name)
        if handler is None:
            _LOGGER.warning("No handler registered for task '%s'", message.name)
            return
        try:
            await handler(message)
        except Exception:  # pragma: no cover - defensive catch-all
            _LOGGER.exception("Task '%s' handler failed", message.name)

    async def run(self, *, shutdown_event: asyncio.Event | None = None) -> None:
        """Consume messages from the queue until ``shutdown_event`` is set."""

        stop_event = shutdown_event or asyncio.Event()
        self._queue.subscribe(self._subscriber)
        _LOGGER.info("Job worker started; waiting for tasks.")
        try:
            await stop_event.wait()
        finally:
            self._queue.unsubscribe(self._subscriber)
            _LOGGER.info("Job worker stopped.")


def create_worker(queue: TaskQueue) -> JobWorker:
    """Return a configured :class:`JobWorker` for ``queue``."""

    return JobWorker(queue)


async def serve(
    queue: TaskQueue,
    *,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    """Run a worker that consumes messages from ``queue``."""

    worker = JobWorker(queue)
    await worker.run(shutdown_event=shutdown_event)


def main() -> None:
    """CLI helper for launching a standalone worker process."""

    settings = get_settings()
    setup_logging(settings)
    ensure_runtime_dirs(settings)

    queue = TaskQueue()
    try:
        asyncio.run(serve(queue))
    except KeyboardInterrupt:  # pragma: no cover - manual shutdown path
        _LOGGER.info("Job worker interrupted; exiting.")


__all__ = ["JobWorker", "TaskProcessor", "create_worker", "serve", "main"]

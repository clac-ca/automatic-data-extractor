"""In-memory coordinator for asynchronous ADE run execution streams."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ade_api.common.logging import log_context

if TYPE_CHECKING:
    from .service import RunStreamFrame

__all__ = ["RunExecutionSupervisor"]


class _RunGenerator(Protocol):
    async def __call__(self) -> AsyncIterator[RunStreamFrame]:
        ...


@dataclass(slots=True)
class _RunHandle:
    queue: asyncio.Queue[object]
    task: asyncio.Task[None]


_COMPLETE = object()
logger = logging.getLogger(__name__)


class RunExecutionSupervisor:
    """Coordinate background execution streams for ADE runs.

    The supervisor ensures the engine subprocess executes outside the request
    scope while allowing callers to consume the run stream lazily. Each run
    maintains a dedicated queue populated by a background task that consumes the
    provided async generator.
    """

    def __init__(self) -> None:
        self._handles: dict[str, _RunHandle] = {}
        self._lock = asyncio.Lock()

    async def stream(
        self, run_id: str, *, generator: _RunGenerator
    ) -> AsyncIterator[RunStreamFrame]:
        """Return an iterator for ``run_id`` backed by a background task."""

        handle = await self._ensure_handle(run_id, generator)
        logger.debug(
            "run.supervisor.stream.start",
            extra=log_context(run_id=run_id),
        )
        try:
            while True:
                item = await handle.queue.get()
                if item is _COMPLETE:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item  # type: ignore[misc]
        finally:
            await self._finalize(run_id)
            logger.debug(
                "run.supervisor.stream.end",
                extra=log_context(run_id=run_id),
            )

    async def _ensure_handle(
        self, run_id: str, generator: _RunGenerator
    ) -> _RunHandle:
        async with self._lock:
            existing = self._handles.get(run_id)
            if existing is not None:
                return existing

            queue: asyncio.Queue[object] = asyncio.Queue()
            task = asyncio.create_task(self._drive(run_id, generator, queue))
            handle = _RunHandle(queue=queue, task=task)
            self._handles[run_id] = handle
            logger.debug(
                "run.supervisor.handle.created",
                extra=log_context(run_id=run_id),
            )
            return handle

    async def _drive(
        self,
        run_id: str,
        generator_factory: _RunGenerator,
        queue: asyncio.Queue[object],
    ) -> None:
        try:
            async for frame in generator_factory():
                await queue.put(frame)
        except Exception as exc:  # pragma: no cover - surfaced to consumers
            logger.exception(
                "run.supervisor.drive.error",
                extra=log_context(run_id=run_id),
            )
            await queue.put(exc)
        finally:
            await queue.put(_COMPLETE)

    async def _finalize(self, run_id: str) -> None:
        handle = self._handles.pop(run_id, None)
        if handle is None:
            return
        handle.task.cancel()
        try:
            await asyncio.shield(handle.task)
        except Exception:
            # Exceptions are surfaced to consumers via the queue; suppressing
            # here prevents duplicate propagation while still allowing the
            # caller's ``async for`` to react accordingly.
            pass

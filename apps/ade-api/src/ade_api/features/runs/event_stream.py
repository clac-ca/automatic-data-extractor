from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ade_api.schemas.event_record import (
    EventRecord,
    EventRecordLog,
    coerce_event_record,
    ensure_event_context,
)

__all__ = [
    "RunEventContext",
    "RunEventStream",
    "RunEventStreamRegistry",
    "RunEventSubscription",
]


@dataclass(slots=True)
class RunEventContext:
    """Minimal identifiers used to enrich events as they are appended."""

    job_id: str | None = None
    workspace_id: str | None = None
    build_id: str | None = None
    configuration_id: str | None = None


class RunEventSubscription:
    """Async iterator bound to a RunEventStream subscription queue."""

    def __init__(self, queue: asyncio.Queue[EventRecord | None], on_close: callable[[], None]) -> None:
        self._queue = queue
        self._on_close = on_close

    def __aiter__(self) -> AsyncIterator[EventRecord]:
        return self

    async def __anext__(self) -> EventRecord:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        self._on_close()
        await self._queue.put(None)

    async def __aenter__(self) -> RunEventSubscription:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()


class RunEventStream:
    """Append-only NDJSON sink with in-memory subscribers for SSE."""

    def __init__(self, *, path: Path, context: RunEventContext | None = None) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._context = context or RunEventContext()
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue[EventRecord | None]] = set()

    @property
    def path(self) -> Path:
        return self._path

    def update_context(self, *, context: RunEventContext) -> None:
        self._context.job_id = self._context.job_id or context.job_id
        self._context.workspace_id = self._context.workspace_id or context.workspace_id
        self._context.build_id = self._context.build_id or context.build_id
        self._context.configuration_id = (
            self._context.configuration_id or context.configuration_id
        )

    def iter_persisted(self, *, after_sequence: int | None = None) -> Iterable[EventRecord]:
        """Yield events from disk, skipping up to ``after_sequence`` entries."""

        log = EventRecordLog(str(self._path))
        return log.iter(after_sequence=after_sequence)

    def last_cursor(self) -> int:
        """Return the count of events observed on disk."""

        return EventRecordLog(str(self._path)).last_cursor()

    async def append(self, event: EventRecord | Any) -> EventRecord:
        """Persist an event to NDJSON and fan-out to subscribers."""

        record = coerce_event_record(event)
        if record is None:
            raise ValueError("Unable to append non-event payload to RunEventStream")

        record.pop("sequence", None)
        record = ensure_event_context(
            record,
            job_id=self._context.job_id,
            workspace_id=self._context.workspace_id,
            build_id=self._context.build_id,
            configuration_id=self._context.configuration_id,
        )

        async with self._lock:
            serialized = json.dumps(
                record,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
            await asyncio.to_thread(self._append_line, serialized)
            await self._publish(record)
            return record

    async def _publish(self, event: EventRecord) -> None:
        to_remove: list[asyncio.Queue[EventRecord | None]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except Exception:
                to_remove.append(queue)
        for queue in to_remove:
            self._subscribers.discard(queue)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[RunEventSubscription]:
        queue: asyncio.Queue[EventRecord | None] = asyncio.Queue()
        self._subscribers.add(queue)

        def _on_close() -> None:
            self._subscribers.discard(queue)

        subscription = RunEventSubscription(queue, _on_close)
        try:
            yield subscription
        finally:
            await subscription.aclose()

    def _append_line(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")


class RunEventStreamRegistry:
    """Shared registry for RunEventStream instances keyed by file path."""

    def __init__(self) -> None:
        self._streams: dict[str, RunEventStream] = {}

    def get_stream(self, *, path: Path, context: RunEventContext) -> RunEventStream:
        key = str(path.resolve())
        stream = self._streams.get(key)
        if stream is None:
            stream = RunEventStream(path=path, context=context)
            self._streams[key] = stream
        else:
            stream.update_context(context=context)
        return stream

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ade_engine.schemas import AdeEvent, AdeEventPayload
from pydantic import BaseModel

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.infra.storage import workspace_run_root
from ade_api.settings import Settings

__all__ = [
    "RunEventDispatcher",
    "RunEventLogReader",
    "RunEventStorage",
    "RunEventSubscription",
]


@dataclass(slots=True)
class RunEventSubscription:
    """Live stream handle for a run's event stream."""

    run_id: str
    _queue: asyncio.Queue[AdeEvent | None]
    _on_close: Callable[[str, asyncio.Queue[AdeEvent | None]], None]
    _closed: bool = False

    def __aiter__(self) -> AsyncIterator[AdeEvent]:
        return self

    async def __anext__(self) -> AdeEvent:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._on_close(self.run_id, self._queue)
        await self._queue.put(None)


class RunEventStorage:
    """Persist AdeEvents to NDJSON files per run and replay them."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def events_path(self, *, workspace_id: str, run_id: str, create: bool = True) -> Path:
        run_dir = workspace_run_root(self._settings, workspace_id, run_id)
        logs_dir = run_dir / "logs"
        if create:
            logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / "events.ndjson"

    async def append(self, event: AdeEvent) -> AdeEvent:
        if not event.workspace_id or not event.run_id:
            raise ValueError("workspace_id and run_id are required to append events")

        path = self.events_path(workspace_id=event.workspace_id, run_id=event.run_id)
        serialized = event.model_dump_json()
        await asyncio.to_thread(self._append_line, path, serialized)
        return event

    def iter_events(
        self,
        *,
        workspace_id: str,
        run_id: str,
        after_sequence: int | None = None,
    ) -> Iterable[AdeEvent]:
        path = self.events_path(workspace_id=workspace_id, run_id=run_id, create=False)

        def _iter() -> Iterable[AdeEvent]:
            if not path.exists():
                return
            with path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    if not raw.strip():
                        continue
                    event = AdeEvent.model_validate_json(raw)
                    if after_sequence is not None and event.sequence is not None:
                        if event.sequence <= after_sequence:
                            continue
                    yield event

        return _iter()

    def last_sequence(self, *, workspace_id: str, run_id: str) -> int:
        last_seen = 0
        for event in self.iter_events(workspace_id=workspace_id, run_id=run_id):
            if event.sequence:
                last_seen = max(last_seen, event.sequence)
        return last_seen

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")


class RunEventDispatcher:
    """Assign event IDs/sequences, persist to NDJSON, and fan-out to subscribers."""

    def __init__(
        self,
        *,
        storage: RunEventStorage,
        id_factory: Callable[[], str] = generate_uuid7,
    ) -> None:
        self.storage = storage
        self._id_factory = id_factory
        self._sequence_by_run: dict[str, int] = {}
        self._subscribers: dict[str, set[asyncio.Queue[AdeEvent | None]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def emit(
        self,
        *,
        type: str,
        workspace_id: str,
        configuration_id: str,
        run_id: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        source: str = "api",
        build_id: str | None = None,
    ) -> AdeEvent:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump()
        sequence = await self._next_sequence(workspace_id=workspace_id, run_id=run_id)
        event = AdeEvent(
            type=type,
            event_id=f"evt_{self._id_factory()}",
            created_at=utc_now(),
            sequence=sequence,
            source=source,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            build_id=build_id,
            payload=payload,
        )
        await self.storage.append(event)
        await self._publish(event)
        return event

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[RunEventSubscription]:
        queue: asyncio.Queue[AdeEvent | None] = asyncio.Queue()
        if run_id not in self._subscribers:
            self._subscribers[run_id] = set()
        self._subscribers[run_id].add(queue)
        subscription = RunEventSubscription(run_id, queue, self._remove_subscriber)
        try:
            yield subscription
        finally:
            await subscription.close()

    async def _publish(self, event: AdeEvent) -> None:
        for queue in list(self._subscribers.get(event.run_id or "", [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def _remove_subscriber(
        self, run_id: str, queue: asyncio.Queue[AdeEvent | None]
    ) -> None:
        subscribers = self._subscribers.get(run_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(run_id, None)

    async def _next_sequence(self, *, workspace_id: str, run_id: str) -> int:
        lock = self._locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            if run_id not in self._sequence_by_run:
                self._sequence_by_run[run_id] = await asyncio.to_thread(
                    self.storage.last_sequence,
                    workspace_id=workspace_id,
                    run_id=run_id,
                )
            self._sequence_by_run[run_id] += 1
            return self._sequence_by_run[run_id]


class RunEventLogReader:
    """Streaming iterator for a run's persisted events."""

    def __init__(self, *, storage: RunEventStorage, workspace_id: str, run_id: str) -> None:
        self._storage = storage
        self._workspace_id = workspace_id
        self._run_id = run_id

    def iter(self, *, after_sequence: int | None = None) -> Iterable[AdeEvent]:
        return self._storage.iter_events(
            workspace_id=self._workspace_id,
            run_id=self._run_id,
            after_sequence=after_sequence,
        )

    def last_sequence(self) -> int:
        return self._storage.last_sequence(
            workspace_id=self._workspace_id,
            run_id=self._run_id,
        )

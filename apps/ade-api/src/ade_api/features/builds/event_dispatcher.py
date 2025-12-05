from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from ade_engine.schemas import AdeEvent, AdeEventPayload
from pydantic import BaseModel

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.infra.storage import build_venv_root
from ade_api.settings import Settings

__all__ = [
    "BuildEventDispatcher",
    "BuildEventLogReader",
    "BuildEventStorage",
    "BuildEventSubscription",
]


@dataclass(slots=True)
class BuildEventSubscription:
    """Live stream handle for a build's event stream."""

    build_id: UUID
    _queue: asyncio.Queue[AdeEvent | None]
    _on_close: Callable[[UUID, asyncio.Queue[AdeEvent | None]], None]
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
        self._on_close(self.build_id, self._queue)
        await self._queue.put(None)


class BuildEventStorage:
    """Persist AdeEvents to NDJSON files per build and replay them."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def events_path(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
        create: bool = True,
    ) -> Path:
        build_root = build_venv_root(
            self._settings,
            str(workspace_id),
            str(configuration_id),
            str(build_id),
        )
        logs_dir = build_root / "logs"
        if create:
            logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / "events.ndjson"

    async def append(self, event: AdeEvent) -> AdeEvent:
        if not event.workspace_id or not event.build_id or not event.configuration_id:
            raise ValueError(
                "workspace_id, configuration_id, and build_id are required to append events"
            )

        path = self.events_path(
            workspace_id=event.workspace_id,
            configuration_id=event.configuration_id,
            build_id=event.build_id,
        )
        serialized = event.model_dump_json()
        await asyncio.to_thread(self._append_line, path, serialized)
        return event

    def iter_events(
        self,
        *,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
        after_sequence: int | None = None,
    ) -> Iterable[AdeEvent]:
        path = self.events_path(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            create=False,
        )

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

    def last_sequence(self, *, workspace_id: UUID, configuration_id: UUID, build_id: UUID) -> int:
        last_seen = 0
        for event in self.iter_events(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        ):
            if event.sequence:
                last_seen = max(last_seen, event.sequence)
        return last_seen

    @staticmethod
    def _append_line(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")


class BuildEventDispatcher:
    """Assign event IDs/sequences, persist to NDJSON, and fan-out to subscribers."""

    def __init__(
        self,
        *,
        storage: BuildEventStorage,
        id_factory: Callable[[], UUID] = generate_uuid7,
    ) -> None:
        self.storage = storage
        self._id_factory = id_factory
        self._sequence_by_build: dict[UUID, int] = {}
        self._subscribers: dict[UUID, set[asyncio.Queue[AdeEvent | None]]] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}

    async def emit(
        self,
        *,
        type: str,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        source: str = "api",
        run_id: UUID | None = None,
    ) -> AdeEvent:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)
        sequence = await self._next_sequence(
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
        )
        event = AdeEvent(
            type=type,
            event_id=f"evt_{self._id_factory()}",
            created_at=utc_now(),
            sequence=sequence,
            source=source,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            run_id=run_id,
            payload=payload,
        )
        await self.storage.append(event)
        await self._publish(event)
        return event

    @asynccontextmanager
    async def subscribe(self, build_id: UUID) -> AsyncIterator[BuildEventSubscription]:
        queue: asyncio.Queue[AdeEvent | None] = asyncio.Queue()
        if build_id not in self._subscribers:
            self._subscribers[build_id] = set()
        self._subscribers[build_id].add(queue)
        subscription = BuildEventSubscription(build_id, queue, self._remove_subscriber)
        try:
            yield subscription
        finally:
            await subscription.close()

    async def _publish(self, event: AdeEvent) -> None:
        if event.build_id is None:
            return
        for queue in list(self._subscribers.get(event.build_id, [])):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

    def _remove_subscriber(
        self, build_id: UUID, queue: asyncio.Queue[AdeEvent | None]
    ) -> None:
        subscribers = self._subscribers.get(build_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(build_id, None)

    async def _next_sequence(
        self, *, workspace_id: UUID, configuration_id: UUID, build_id: UUID
    ) -> int:
        lock = self._locks.setdefault(build_id, asyncio.Lock())
        async with lock:
            if build_id not in self._sequence_by_build:
                self._sequence_by_build[build_id] = await asyncio.to_thread(
                    self.storage.last_sequence,
                    workspace_id=workspace_id,
                    configuration_id=configuration_id,
                    build_id=build_id,
                )
            self._sequence_by_build[build_id] += 1
            return self._sequence_by_build[build_id]


class BuildEventLogReader:
    """Streaming iterator for a build's persisted events."""

    def __init__(
        self,
        *,
        storage: BuildEventStorage,
        workspace_id: UUID,
        configuration_id: UUID,
        build_id: UUID,
    ) -> None:
        self._storage = storage
        self._workspace_id = workspace_id
        self._configuration_id = configuration_id
        self._build_id = build_id

    def iter(self, *, after_sequence: int | None = None) -> Iterable[AdeEvent]:
        return self._storage.iter_events(
            workspace_id=self._workspace_id,
            configuration_id=self._configuration_id,
            build_id=self._build_id,
            after_sequence=after_sequence,
        )

    def last_sequence(self) -> int:
        return self._storage.last_sequence(
            workspace_id=self._workspace_id,
            configuration_id=self._configuration_id,
            build_id=self._build_id,
        )

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from ade_api.common.ids import generate_uuid7
from ade_api.common.time import utc_now
from ade_api.infra.events.ndjson import append_line, iter_events_file
from ade_api.infra.events.scoped_dispatcher import EventSubscription, ScopedEventDispatcher
from ade_api.infra.events.utils import ensure_event_defaults
from ade_api.infra.storage import workspace_run_root
from ade_api.schemas.events import AdeEvent, AdeEventPayload, EngineEventFrame
from ade_api.settings import Settings

__all__ = [
    "RunEventDispatcher",
    "RunEventLogReader",
    "RunEventStorage",
]


class RunEventSubscription(EventSubscription):
    """Backward-compatible alias that exposes ``run_id`` as the scope identifier."""

    @property
    def run_id(self) -> UUID:
        return self.scope_id


class RunEventStorage:
    """Persist AdeEvents to NDJSON files per run and replay them."""

    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def events_path(self, *, workspace_id: UUID, run_id: UUID, create: bool = True) -> Path:
        run_dir = workspace_run_root(self._settings, str(workspace_id), str(run_id))
        logs_dir = run_dir / "logs"
        if create:
            logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / "events.ndjson"

    async def append(self, event: AdeEvent) -> AdeEvent:
        if not event.workspace_id or not event.run_id:
            raise ValueError("workspace_id and run_id are required to append events")

        ensure_event_defaults(event)
        path = self.events_path(workspace_id=event.workspace_id, run_id=event.run_id)
        serialized = event.model_dump_json()
        await asyncio.to_thread(append_line, path, serialized)
        return event

    def iter_events(
        self,
        *,
        workspace_id: UUID,
        run_id: UUID,
        after_sequence: int | None = None,
    ) -> Iterable[AdeEvent]:
        path = self.events_path(workspace_id=workspace_id, run_id=run_id, create=False)
        return iter_events_file(path, after_sequence=after_sequence)

    def last_sequence(self, *, workspace_id: UUID, run_id: UUID) -> int:
        last_seen = 0
        for event in self.iter_events(workspace_id=workspace_id, run_id=run_id):
            if event.sequence:
                last_seen = max(last_seen, event.sequence)
        return last_seen


class RunEventDispatcher(ScopedEventDispatcher):
    """Assign event IDs/sequences, persist to NDJSON, and fan-out to subscribers."""

    def __init__(
        self,
        *,
        storage: RunEventStorage,
        id_factory: Callable[[], UUID] = generate_uuid7,
    ) -> None:
        super().__init__()
        self.storage = storage
        self._id_factory = id_factory

    async def emit(
        self,
        *,
        type: str,
        workspace_id: UUID,
        configuration_id: UUID,
        run_id: UUID,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        source: str = "api",
        build_id: UUID | None = None,
        origin_event_id: str | None = None,
    ) -> AdeEvent:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)
        payload = payload or {}
        sequence = await self.next_sequence(
            run_id,
            last_sequence=lambda: self.storage.last_sequence(
                workspace_id=workspace_id,
                run_id=run_id,
            ),
        )
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
            origin_event_id=origin_event_id,
            payload=payload,
        )
        await self.storage.append(event)
        await self.publish(run_id, event)
        return event

    async def emit_from_engine_frame(
        self,
        *,
        frame: EngineEventFrame,
        workspace_id: UUID,
        configuration_id: UUID,
        run_id: UUID,
        build_id: UUID | None = None,
    ) -> AdeEvent:
        payload = dict(frame.payload or {})
        if frame.meta:
            payload.setdefault("meta", frame.meta)
        return await self.emit(
            type=frame.type,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            build_id=build_id,
            payload=payload,
            source="engine",
            origin_event_id=str(frame.event_id),
        )

    @asynccontextmanager
    async def subscribe(self, run_id: UUID) -> AsyncIterator[RunEventSubscription]:
        async with self.subscribe_scope(
            run_id,
            subscription_factory=RunEventSubscription,
        ) as subscription:
            yield subscription


class RunEventLogReader:
    """Streaming iterator for a run's persisted events."""

    def __init__(self, *, storage: RunEventStorage, workspace_id: UUID, run_id: UUID) -> None:
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
        return self._storage.last_sequence(workspace_id=self._workspace_id, run_id=self._run_id)

from __future__ import annotations

from typing import Any

from ade_engine.schemas import (
    AdeEvent,
    AdeEventPayload,
    ConsoleLinePayload,
    RunQueuedPayload,
    RunStartedPayload,
)

from ade_api.infra.events.base import BaseEventEmitter


class RunEventEmitter(BaseEventEmitter):
    """Typed helper for run-scoped events."""

    def __init__(
        self,
        dispatcher,
        *,
        workspace_id: Any,
        configuration_id: Any,
        run_id: Any,
        build_id: Any | None = None,
        source: str = "api",
    ) -> None:
        super().__init__(
            dispatcher,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            run_id=run_id,
            build_id=build_id,
            source=source,
        )

    async def console_line(self, payload: ConsoleLinePayload) -> AdeEvent:
        return await self.emit(type="console.line", payload=payload)

    async def queued(self, *, mode: str, options: dict[str, Any]) -> AdeEvent:
        payload = RunQueuedPayload(status="queued", mode=mode, options=options).model_dump(exclude_none=True)
        return await self.emit_prefixed(prefix="run", suffix="queued", payload=payload)

    async def start(
        self,
        *,
        mode: str,
        engine_version: str | None = None,
        config_version: str | None = None,
    ) -> AdeEvent:
        payload = RunStartedPayload(
            status="in_progress",
            mode=mode,
            engine_version=engine_version,
            config_version=config_version,
        ).model_dump(exclude_none=True)
        return await self.emit_prefixed(prefix="run", suffix="start", payload=payload)

    async def complete(
        self,
        payload: AdeEventPayload | dict[str, Any],
    ) -> AdeEvent:
        return await self.emit_prefixed(prefix="run", suffix="complete", payload=payload)

    async def custom(
        self,
        type_suffix: str,
        *,
        payload: AdeEventPayload | dict[str, Any] | None = None,
    ) -> AdeEvent:
        return await self.emit_prefixed(
            prefix="run",
            suffix=type_suffix,
            payload=payload,
        )


__all__ = ["RunEventEmitter"]

from __future__ import annotations

from typing import Any

from ade_engine.schemas import AdeEvent, AdeEventPayload, ConsoleLinePayload

from ade_api.infra.events.base import BaseEventEmitter


class BuildEventEmitter(BaseEventEmitter):
    """Typed helper for build-scoped events."""

    def __init__(
        self,
        dispatcher,
        *,
        workspace_id: Any,
        configuration_id: Any,
        build_id: Any,
        source: str = "api",
        run_id: Any | None = None,
    ) -> None:
        super().__init__(
            dispatcher,
            workspace_id=workspace_id,
            configuration_id=configuration_id,
            build_id=build_id,
            run_id=run_id,
            source=source,
        )

    async def console_line(self, payload: ConsoleLinePayload) -> AdeEvent:
        return await self.emit(type="console.line", payload=payload)

    async def custom(
        self,
        type_suffix: str,
        *,
        payload: AdeEventPayload | dict[str, Any] | None = None,
    ) -> AdeEvent:
        return await self.emit_prefixed(
            prefix="build",
            suffix=type_suffix,
            payload=payload,
        )

    async def emit_raw(
        self,
        type_name: str,
        *,
        payload: AdeEventPayload | dict[str, Any] | None = None,
    ) -> AdeEvent:
        return await self.emit(
            type=type_name,
            payload=payload,
        )


__all__ = ["BuildEventEmitter"]

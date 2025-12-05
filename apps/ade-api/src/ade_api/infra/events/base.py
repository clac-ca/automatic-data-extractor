from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ade_api.schemas.events import AdeEvent, AdeEventPayload


class BaseEventEmitter:
    """Lightweight dispatcher wrapper that injects common IDs."""

    def __init__(
        self,
        dispatcher: Any,
        *,
        workspace_id: Any,
        configuration_id: Any,
        run_id: Any | None = None,
        build_id: Any | None = None,
        source: str = "api",
    ) -> None:
        self._dispatcher = dispatcher
        self._ids = {
            "workspace_id": workspace_id,
            "configuration_id": configuration_id,
            "run_id": run_id,
            "build_id": build_id,
        }
        self._source = source

    async def emit(
        self,
        *,
        type: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        source: str | None = None,
        extra_ids: dict[str, Any] | None = None,
    ) -> AdeEvent:
        if isinstance(payload, BaseModel):
            payload = payload.model_dump(exclude_none=True)

        ids = dict(self._ids)
        if extra_ids:
            ids.update({k: v for k, v in extra_ids.items() if v is not None})

        return await self._dispatcher.emit(
            type=type,
            payload=payload,
            source=source or self._source,
            workspace_id=ids.get("workspace_id"),
            configuration_id=ids.get("configuration_id"),
            run_id=ids.get("run_id"),
            build_id=ids.get("build_id"),
        )

    async def emit_prefixed(
        self,
        *,
        prefix: str,
        suffix: str,
        payload: AdeEventPayload | dict[str, Any] | None = None,
        source: str | None = None,
        extra_ids: dict[str, Any] | None = None,
    ) -> AdeEvent:
        type_name = suffix if suffix.startswith(f"{prefix}.") else f"{prefix}.{suffix}"
        return await self.emit(
            type=type_name,
            payload=payload,
            source=source,
            extra_ids=extra_ids,
        )


__all__ = ["BaseEventEmitter"]

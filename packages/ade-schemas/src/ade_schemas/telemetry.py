"""Telemetry envelope schemas shared across ADE components."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ADE_TELEMETRY_EVENT_SCHEMA = "ade.telemetry/run-event.v1"

TelemetryLevel = Literal["debug", "info", "warning", "error", "critical"]


class TelemetryEvent(BaseModel):
    """Event payload emitted by the engine runtime."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(alias="event")
    level: TelemetryLevel = "info"

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class TelemetryEnvelope(BaseModel):
    """Versioned envelope for ADE telemetry events."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema: Literal[ADE_TELEMETRY_EVENT_SCHEMA] = ADE_TELEMETRY_EVENT_SCHEMA
    version: str = Field(default="1.0.0")
    job_id: str
    run_id: str | None = None
    emitted_at: datetime = Field(alias="timestamp")
    event: TelemetryEvent

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(*args, **kwargs)


__all__ = [
    "ADE_TELEMETRY_EVENT_SCHEMA",
    "TelemetryEnvelope",
    "TelemetryEvent",
    "TelemetryLevel",
]

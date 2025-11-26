"""Unified ADE event envelope (ade.event/v1)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ADE_EVENT_SCHEMA = "ade.event/v1"


class AdeEvent(BaseModel):
    """ADE event envelope used for engine telemetry, runs, and builds."""

    type: str
    object: Literal["ade.event"] = Field(default="ade.event", alias="object")
    schema: Literal["ade.event/v1"] = Field(default=ADE_EVENT_SCHEMA)
    version: str = "1.0.0"
    created_at: datetime

    workspace_id: str | None = None
    configuration_id: str | None = None
    run_id: str | None = None
    build_id: str | None = None

    run: dict[str, Any] | None = None
    build: dict[str, Any] | None = None
    env: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    output_delta: dict[str, Any] | None = None
    log: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


# Legacy exports (kept for import compatibility; prefer AdeEvent)
TelemetryEnvelope = AdeEvent


class TelemetryEvent(BaseModel):  # pragma: no cover - legacy placeholder
    event: str
    level: str
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


__all__ = [
    "ADE_EVENT_SCHEMA",
    "AdeEvent",
    "TelemetryEnvelope",
    "TelemetryEvent",
]

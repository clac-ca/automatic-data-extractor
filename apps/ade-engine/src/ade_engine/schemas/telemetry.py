"""Telemetry event schema models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


ADE_TELEMETRY_EVENT_SCHEMA = "ade.telemetry/run-event.v1"


class TelemetryEvent(BaseModel):
    """Single telemetry event payload."""

    event: str
    level: str
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class TelemetryEnvelope(BaseModel):
    """Envelope wrapping telemetry events with run context."""

    schema: str = Field(default=ADE_TELEMETRY_EVENT_SCHEMA)
    version: str = Field(default="1.0.0")
    run_id: str
    timestamp: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    event: TelemetryEvent

    model_config = ConfigDict(extra="forbid")


__all__ = [
    "ADE_TELEMETRY_EVENT_SCHEMA",
    "TelemetryEnvelope",
    "TelemetryEvent",
]

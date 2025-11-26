"""Unified ADE event envelope (ade.event/v1).

This module defines the common event envelope used for engine telemetry,
run/build streaming, and analytics. Everything beyond the common fields is
type-specific payload keyed off ``type``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


ADE_EVENT_SCHEMA = "ade.event/v1"


class AdeEvent(BaseModel):
    """ADE event envelope used for engine telemetry, runs, and builds.

    This schema intentionally mirrors the ``ade.event/v1`` envelope described in
    the event model docs. Additional event-specific fields are allowed and kept
    flat at the top level.
    """

    # Primary discriminator for downstream consumers.
    type: str

    # Optional object tag for consumers that rely on a common OpenAI-style
    # pattern. Kept for forward-compatibility, but not required by the ADE spec.
    object: Literal["ade.event"] = Field(default="ade.event", alias="object")

    # Schema and versioning.
    schema_id: Literal["ade.event/v1"] = Field(
        default=ADE_EVENT_SCHEMA,
        alias="schema",
        validation_alias=AliasChoices("schema", "schema_id"),
    )
    version: str = "1.0.0"

    # Timestamp in UTC.
    created_at: datetime

    # Ordering within a single run/build/job stream.
    sequence: int | None = None

    # Correlation context (nullable when not applicable).
    workspace_id: str | None = None
    configuration_id: str | None = None
    job_id: str | None = None
    run_id: str | None = None
    build_id: str | None = None

    # Event producer and cross-cutting metadata.
    source: str | None = None
    details: dict[str, Any] | None = None

    # Optional error payload for failure events (e.g. run.completed, build.completed).
    error: dict[str, Any] | None = None

    # Everything else is event-type-specific.
    model_config = ConfigDict(populate_by_name=True, extra="allow")


# Legacy exports (kept for import compatibility; prefer AdeEvent).
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

"""Pydantic schemas for the health module."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from ade_api.common.schema import BaseSchema


class HealthComponentStatus(BaseSchema):
    """Represents the health of an individual system component."""

    name: str = Field(..., description="Component identifier.")
    status: Literal["available", "degraded", "unavailable"] = Field(
        ..., description="High-level component status flag."
    )
    detail: str | None = Field(
        default=None,
        description="Optional human-readable note about the component state.",
    )


class HealthCheckResponse(BaseSchema):
    """Top-level payload returned by the `/health` endpoint."""

    status: Literal["ok", "error"] = Field(
        ..., description="Overall system health indicator."
    )
    timestamp: datetime = Field(..., description="UTC timestamp for when the check executed.")
    components: list[HealthComponentStatus] = Field(
        default_factory=list,
        description="Detailed component-level status information.",
    )

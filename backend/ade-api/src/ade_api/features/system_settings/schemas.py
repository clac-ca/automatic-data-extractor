"""Pydantic schemas for system-wide settings controls."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SafeModeStatus(BaseModel):
    """Represents the current safe mode state."""

    enabled: bool = Field(description="Whether ADE is short-circuiting user runs")
    detail: str = Field(description="User-visible explanation of the safe mode status")


class SafeModeUpdateRequest(BaseModel):
    """Request payload for toggling safe mode."""

    enabled: bool = Field(description="Updated safe mode state")
    detail: str | None = Field(
        default=None, description="Optional message describing the active state"
    )


__all__ = ["SafeModeStatus", "SafeModeUpdateRequest"]

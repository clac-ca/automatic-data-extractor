from __future__ import annotations

from pydantic import BaseModel, Field


class DetectorSettings(BaseModel):
    """Column/row detector sampling settings."""

    row_sample_size: int = Field(default=1000, ge=1)
    text_sample_size: int = Field(default=200, ge=1)


__all__ = ["DetectorSettings"]


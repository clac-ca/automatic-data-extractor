from __future__ import annotations

from pydantic import BaseModel, Field


class DetectorSettings(BaseModel):
    """Detector sampling settings (detection stage only)."""

    detector_column_sample_size: int = Field(
        default=100,
        ge=1,
    )


__all__ = ["DetectorSettings"]

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic.aliases import AliasChoices


class DetectorSettings(BaseModel):
    """Detector sampling settings (detection stage only)."""

    detector_max_table_rows: int = Field(
        default=1000,
        ge=1,
        validation_alias=AliasChoices("detector_max_table_rows", "row_sample_size"),
    )
    detector_column_sample_size: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices("detector_column_sample_size", "text_sample_size"),
    )

    @property
    def row_sample_size(self) -> int:  # pragma: no cover - compatibility alias
        return self.detector_max_table_rows

    @property
    def text_sample_size(self) -> int:  # pragma: no cover - compatibility alias
        return self.detector_column_sample_size


__all__ = ["DetectorSettings"]

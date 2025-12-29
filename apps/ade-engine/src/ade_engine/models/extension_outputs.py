from __future__ import annotations

import math

from pydantic import RootModel, field_validator


class _BaseDetectorResult(RootModel[dict[str, float]]):
    @property
    def scores(self) -> dict[str, float]:
        return self.root

    @field_validator("root")
    @classmethod
    def validate_scores(cls, scores: dict[str, float]) -> dict[str, float]:
        validated: dict[str, float] = {}
        for key, raw_value in scores.items():
            if not isinstance(key, str):
                raise TypeError("score keys must be strings")
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise TypeError(f"score for '{key}' must be numeric") from exc
            if not math.isfinite(value):
                raise ValueError(f"score for '{key}' must be finite")
            validated[key] = value
        return validated


class RowDetectorResult(_BaseDetectorResult):
    """Row detector output: mapping of row kind → score."""


class ColumnDetectorResult(_BaseDetectorResult):
    """Column detector output: mapping of field name → score."""


__all__ = [
    "ColumnDetectorResult",
    "RowDetectorResult",
]

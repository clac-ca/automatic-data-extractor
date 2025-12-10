from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, RootModel, field_validator


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


class _BaseRowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_index: int

    @field_validator("row_index")
    @classmethod
    def validate_row_index(cls, row_index: int) -> int:
        if isinstance(row_index, bool):
            raise TypeError("row_index must be an integer")
        if row_index < 0:
            raise ValueError("row_index must be >= 0")
        return row_index


class CellTransformResult(_BaseRowResult):
    value: dict | None

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: dict | None) -> dict | None:
        if value is not None and not isinstance(value, dict):
            raise TypeError("value must be a dict or None")
        return value


class ColumnTransformResult(CellTransformResult):
    """Column transform output for a single row."""


class CellValidatorResult(_BaseRowResult):
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, message: str) -> str:
        if not isinstance(message, str):
            raise TypeError("message must be a string")
        text = message.strip()
        if not text:
            raise ValueError("message must be a nonempty string")
        return message


class ColumnValidatorResult(CellValidatorResult):
    """Column validator output for a single row."""


__all__ = [
    "CellTransformResult",
    "CellValidatorResult",
    "ColumnDetectorResult",
    "ColumnTransformResult",
    "ColumnValidatorResult",
    "RowDetectorResult",
]

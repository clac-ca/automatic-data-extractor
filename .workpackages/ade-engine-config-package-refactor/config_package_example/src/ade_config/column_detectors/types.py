from __future__ import annotations

from typing import TypeAlias, TypedDict


ScoreMap: TypeAlias = dict[str, float]


class ColumnTransformRow(TypedDict):
    row_index: int
    value: dict | None


class ColumnValidatorIssue(TypedDict):
    row_index: int
    message: str


__all__ = ["ScoreMap", "ColumnTransformRow", "ColumnValidatorIssue"]

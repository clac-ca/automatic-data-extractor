from __future__ import annotations

from typing import Any, Mapping, Tuple

from sqlalchemy.sql.elements import ColumnElement

OrderBy = Tuple[ColumnElement[Any], ...]
SortAllowedMap = Mapping[str, Tuple[ColumnElement[Any], ColumnElement[Any]]]

__all__ = ["OrderBy", "SortAllowedMap"]

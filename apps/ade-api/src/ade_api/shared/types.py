from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.sql.elements import ColumnElement

OrderBy = tuple[ColumnElement[Any], ...]
SortAllowedMap = Mapping[str, tuple[ColumnElement[Any], ColumnElement[Any]]]

__all__ = ["OrderBy", "SortAllowedMap"]

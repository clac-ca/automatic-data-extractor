"""Helpers for configuring SQLAlchemy Enum columns."""

from __future__ import annotations

from enum import Enum
from typing import Type


def enum_values(enum_cls: Type[Enum]) -> list[str]:
    """Return the list of values for ``enum_cls`` suitable for SAEnum."""

    return [member.value for member in enum_cls]


__all__ = ["enum_values"]

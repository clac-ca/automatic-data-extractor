"""Helpers for configuring SQLAlchemy Enum columns."""

from __future__ import annotations

from enum import Enum


def enum_values(enum_cls: type[Enum]) -> list[str]:
    """Return the list of values for ``enum_cls`` suitable for SAEnum."""

    return [member.value for member in enum_cls]


__all__ = ["enum_values"]

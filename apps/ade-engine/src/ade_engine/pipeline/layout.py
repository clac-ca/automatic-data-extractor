"""Simple placement policy for output worksheets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SheetLayout:
    next_row: int = 1
    blank_rows_between_tables: int = 1


__all__ = ["SheetLayout"]

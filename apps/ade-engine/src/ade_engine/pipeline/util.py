"""Small pipeline utility helpers."""

from __future__ import annotations


def unique_sheet_name(name: str, used: set[str]) -> str:
    """Return an Excel-safe sheet name unique across the workbook."""

    if name not in used:
        used.add(name)
        return name

    counter = 2
    max_length = 31
    while True:
        suffix = f"-{counter}"
        base_limit = max_length - len(suffix)
        base = name[:base_limit] if base_limit > 0 else name[:max_length]
        candidate = f"{base}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        counter += 1


__all__ = ["unique_sheet_name"]

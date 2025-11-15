"""Input discovery and ingestion helpers."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import openpyxl


def list_input_files(input_dir: Path) -> list[Path]:
    """Return sorted job input files limited to CSV/XLSX types."""

    if not input_dir.exists():
        return []
    candidates = [
        path
        for path in sorted(input_dir.iterdir())
        if path.suffix.lower() in {".csv", ".xlsx"}
    ]
    return [path for path in candidates if path.is_file()]


def read_table(path: Path) -> tuple[list[str], list[list[Any]]]:
    """Read a CSV or XLSX file returning the header row and data rows."""

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = list(csv.reader(handle))
    else:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            reader = [
                [cell.value if cell.value is not None else "" for cell in row]
                for row in sheet
            ]
        finally:
            workbook.close()

    if not reader:
        raise RuntimeError(f"Input file '{path.name}' is empty")

    header, *data = reader
    return [str(value) if value is not None else "" for value in header], [
        [value for value in row]
        for row in data
    ]


def sheet_name(stem: str) -> str:
    """Normalize worksheet names to Excel-safe identifiers."""

    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", stem).strip()
    cleaned = cleaned or "Sheet"
    return cleaned[:31]


__all__ = ["list_input_files", "read_table", "sheet_name"]

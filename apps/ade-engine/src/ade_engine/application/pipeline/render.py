from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence

from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter

from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.table import MappedColumn, SourceColumn, TableData


@dataclass
class SheetWriter:
    """Simple worksheet writer that tracks an explicit row cursor.

    openpyxl's ``Worksheet.append`` advances an internal cursor even when appending
    an empty row; ``max_row`` does not. Tracking our own cursor keeps output ranges
    accurate without relying on openpyxl internals.
    """

    worksheet: Worksheet
    row: int = 0  # last written row index (1-based); 0 means "nothing written yet"

    def write_row(self, values: Sequence[Any]) -> int:
        self.worksheet.append(list(values))
        self.row += 1
        return self.row

    def blank_row(self) -> int:
        return self.write_row([])


def render_table(
    *,
    table: TableData,
    writer: SheetWriter,
    settings: Settings,
    field_order: list[str] | None = None,
    logger: RunLogger,
) -> None:
    """Write a normalized table to ``worksheet`` following ordering rules."""

    mapped_cols: List[MappedColumn] = table.mapped_columns
    unmapped_cols: List[SourceColumn] = table.unmapped_columns if settings.append_unmapped_columns else []

    start_row = writer.row + 1

    # Headers
    canonical_fields = field_order or [col.field_name for col in mapped_cols]
    headers: List[Any] = list(canonical_fields)
    for col in unmapped_cols:
        prefix = settings.unmapped_prefix or "raw_"
        header = str(col.header) if col.header not in (None, "") else f"col_{col.index + 1}"
        headers.append(f"{prefix}{header}")

    writer.write_row(headers)

    # Include unmapped columns when determining how many data rows to emit; otherwise
    # sheets with only unmapped columns would collapse to a header-only table.
    row_count_candidates = [table.row_count, *(len(col.values) for col in unmapped_cols)]
    row_count = max(row_count_candidates)
    for row_idx in range(row_count):
        row_values: List[Any] = []
        for field in canonical_fields:
            col = table.columns.get(field)
            row_values.append(col[row_idx] if col is not None and row_idx < len(col) else None)
        for col in unmapped_cols:
            row_values.append(col.values[row_idx] if row_idx < len(col.values) else None)
        writer.write_row(row_values)

    rows_written = 1 + row_count
    col_count = len(headers)
    if col_count > 0 and rows_written > 0:
        end_row = start_row + rows_written - 1
        end_col = get_column_letter(col_count)
        output_range = f"A{start_row}:{end_col}{end_row}"
    else:
        output_range = ""

    logger.event(
        "table.written",
        message=f"Rendered table with {len(canonical_fields)} canonical columns and {len(unmapped_cols)} unmapped",
        data={
            "sheet_name": writer.worksheet.title,
            "table_index": table.table_index,
            "output_range": output_range,
        },
    )


__all__ = ["SheetWriter", "render_table"]

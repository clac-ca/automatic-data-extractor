from __future__ import annotations

from typing import Any, List

from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter

from ade_engine.pipeline.models import MappedColumn, SourceColumn, TableData
from ade_engine.settings import Settings
from ade_engine.logging import RunLogger


def _next_append_row(worksheet: Worksheet) -> int:
    current = getattr(worksheet, "_current_row", None)
    if isinstance(current, int) and current >= 0:
        return current + 1
    return max(int(getattr(worksheet, "max_row", 0)), 0) + 1


def render_table(
    *,
    table: TableData,
    worksheet: Worksheet,
    settings: Settings,
    field_order: list[str] | None = None,
    logger: RunLogger,
) -> None:
    """Write a normalized table to ``worksheet`` following ordering rules."""

    mapped_cols: List[MappedColumn] = table.mapped_columns
    unmapped_cols: List[SourceColumn] = table.unmapped_columns if settings.append_unmapped_columns else []

    start_row = _next_append_row(worksheet)

    # Headers
    canonical_fields = field_order or [col.field_name for col in mapped_cols]
    headers: List[Any] = list(canonical_fields)
    for col in unmapped_cols:
        prefix = settings.unmapped_prefix or "raw_"
        header = str(col.header) if col.header not in (None, "") else f"col_{col.index + 1}"
        headers.append(f"{prefix}{header}")

    worksheet.append(headers)

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
        worksheet.append(row_values)

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
            "sheet_name": worksheet.title,
            "table_index": table.table_index,
            "output_range": output_range,
        },
    )


__all__ = ["render_table"]

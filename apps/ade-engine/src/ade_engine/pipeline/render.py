from __future__ import annotations

from typing import Any, List

from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.pipeline.models import MappedColumn, SourceColumn, TableData
from ade_engine.settings import Settings
from ade_engine.logging import RunLogger


def render_table(
    *,
    table: TableData,
    worksheet: Worksheet,
    settings: Settings,
    table_index: int = 0,
    logger: RunLogger,
) -> None:
    """Write a normalized table to ``worksheet`` following ordering rules."""

    mapped_cols: List[MappedColumn] = table.mapped_columns
    unmapped_cols: List[SourceColumn] = table.unmapped_columns if settings.append_unmapped_columns else []

    # Headers
    headers: List[Any] = [col.field_name for col in mapped_cols]
    for col in unmapped_cols:
        prefix = settings.unmapped_prefix or "raw_"
        header = str(col.header) if col.header not in (None, "") else f"col_{col.index + 1}"
        headers.append(f"{prefix}{header}")

    worksheet.append(headers)

    # Include unmapped columns when determining how many data rows to emit; otherwise
    # sheets with only unmapped columns would collapse to a header-only table.
    row_count = max((len(col.values) for col in [*mapped_cols, *unmapped_cols]), default=0)
    for row_idx in range(row_count):
        row_values: List[Any] = []
        for col in mapped_cols:
            row_values.append(table.rows[row_idx].get(col.field_name) if row_idx < len(table.rows) else None)
        for col in unmapped_cols:
            row_values.append(col.values[row_idx] if row_idx < len(col.values) else None)
        worksheet.append(row_values)

    logger.event(
        "table.written",
        message=f"Rendered table with {len(mapped_cols)} mapped columns and {len(unmapped_cols)} unmapped",
        data={
            "sheet_name": worksheet.title,
            "table_index": table_index,
            "output_range": worksheet.dimensions,
        },
    )


__all__ = ["render_table"]

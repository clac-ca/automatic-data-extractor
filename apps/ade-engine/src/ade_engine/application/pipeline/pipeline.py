from __future__ import annotations

from datetime import datetime
from typing import Any, List

import polars as pl
from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.application.pipeline.detect_columns import build_source_columns, detect_and_map_columns
from ade_engine.application.pipeline.detect_rows import TableRegion, detect_table_regions
from ade_engine.application.pipeline.render import SheetWriter, render_table
from ade_engine.application.pipeline.transform import apply_transforms
from ade_engine.application.pipeline.validate import apply_validators
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.extension_contexts import HookName
from ade_engine.models.table import TableRegionInfo, TableResult


def _stringify_cell(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _build_table_frame(*, headers: list[str], columns) -> pl.DataFrame:
    """Build a Polars DataFrame from extracted columns, safely handling mixed types."""

    data: dict[str, pl.Series] = {}
    for name, col in zip(headers, columns):
        try:
            data[name] = pl.Series(name, col.values, strict=False)
        except (pl.exceptions.ComputeError, TypeError):
            data[name] = pl.Series(name, [_stringify_cell(v) for v in col.values], dtype=pl.Utf8)
    return pl.DataFrame(data, strict=False)


def _normalize_headers(headers: list[Any], *, start_index: int = 1) -> list[str]:
    """Minimal header normalization (safe for Polars).

    Rules:
    - Convert to string and strip when non-empty; otherwise fall back to ``col_<i>``.
    - Deduplicate collisions in source order by suffixing ``__2``, ``__3``, ...
    """

    seen: dict[str, int] = {}
    out: list[str] = []
    for idx, header in enumerate(headers, start=start_index):
        base = str(header).strip() if header not in (None, "") else f"col_{idx}"
        if not base:
            base = f"col_{idx}"

        count = seen.get(base, 0) + 1
        seen[base] = count
        out.append(base if count == 1 else f"{base}__{count}")
    return out


def _apply_mapping_as_rename(
    *,
    table: pl.DataFrame,
    mapped_source_indices: list[int],
    mapped_field_names: list[str],
    extracted_names_by_index: list[str],
    sheet_name: str,
    table_index: int,
    logger: RunLogger,
) -> tuple[pl.DataFrame, dict[str, str]]:
    if not mapped_source_indices:
        return table, {}

    rename_map: dict[str, str] = {}
    current_names = list(table.columns)
    name_set = set(current_names)

    for source_index, field_name in sorted(zip(mapped_source_indices, mapped_field_names), key=lambda x: x[0]):
        if not (0 <= source_index < len(extracted_names_by_index)):
            continue
        from_name = extracted_names_by_index[source_index]
        to_name = field_name

        if from_name not in name_set:
            continue
        if to_name in name_set:
            logger.warning(
                "Mapping rename collision; skipping rename",
                extra={
                    "data": {
                        "sheet_name": sheet_name,
                        "table_index": table_index,
                        "source_index": source_index,
                        "from_name": from_name,
                        "to_name": to_name,
                    }
                },
            )
            continue

        rename_map[from_name] = to_name
        name_set.remove(from_name)
        name_set.add(to_name)

    if not rename_map:
        return table, {}
    return table.rename(rename_map), rename_map


class Pipeline:
    """Orchestrates sheet-level processing using the registry."""

    def __init__(self, *, registry: Registry, settings: Settings, logger: RunLogger, report_builder=None) -> None:
        self.registry = registry
        self.settings = settings
        self.logger = logger
        self.report_builder = report_builder

    def process_sheet(
        self,
        *,
        sheet: Worksheet,
        output_sheet: Worksheet,
        state: dict,
        metadata: dict,
        input_file_name: str | None = None,
    ) -> list[TableResult]:
        rows, scan = self._materialize_rows_with_scan(sheet)
        writer = SheetWriter(output_sheet)

        if self.report_builder is not None:
            try:
                sheet_index = int(metadata.get("sheet_index", 0)) if isinstance(metadata, dict) else 0
                self.report_builder.record_sheet_scan(sheet_index=sheet_index, sheet_name=sheet.title, scan=scan)
            except Exception:
                self.logger.exception("Failed to record sheet scan for engine.run.completed")

        table_regions = detect_table_regions(
            sheet_name=sheet.title,
            rows=rows,
            registry=self.registry,
            settings=self.settings,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        tables: list[TableResult] = []
        for table_index, region in enumerate(table_regions):
            if table_index > 0:
                writer.blank_row()
            tables.append(
                self._process_table(
                    sheet=sheet,
                    writer=writer,
                    rows=rows,
                    region=region,
                    state=state,
                    metadata=metadata,
                    input_file_name=input_file_name,
                    table_index=table_index,
                )
            )

        return tables

    def _process_table(
        self,
        *,
        sheet: Worksheet,
        writer: SheetWriter,
        rows: List[List[Any]],
        region: TableRegion,
        state: dict,
        metadata: dict,
        input_file_name: str | None,
        table_index: int,
    ) -> TableResult:
        header_row = rows[region.header_row_index] if region.header_row_index < len(rows) else []
        data_rows = rows[region.data_start_row_index:region.data_end_row_index]

        source_cols = build_source_columns(header_row, data_rows)

        extracted_headers = _normalize_headers([c.header for c in source_cols], start_index=1)
        table = _build_table_frame(headers=extracted_headers, columns=source_cols)

        mapped_cols, unmapped_cols, scores_by_column, duplicate_unmapped_indices = detect_and_map_columns(
            sheet_name=sheet.title,
            table=table,
            source_columns=source_cols,
            registry=self.registry,
            settings=self.settings,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        region_info = TableRegionInfo(
            header_row_index=region.header_row_index,
            data_start_row_index=region.data_start_row_index,
            data_end_row_index=region.data_end_row_index,
            header_inferred=region.header_inferred,
        )

        mapped_source_indices = [int(c.source_index) for c in mapped_cols]
        mapped_field_names = [str(c.field_name) for c in mapped_cols]
        table, _rename_map = _apply_mapping_as_rename(
            table=table,
            mapped_source_indices=mapped_source_indices,
            mapped_field_names=mapped_field_names,
            extracted_names_by_index=extracted_headers,
            sheet_name=sheet.title,
            table_index=table_index,
            logger=self.logger,
        )

        maybe_table = self.registry.run_hooks(
            HookName.ON_TABLE_MAPPED,
            settings=self.settings,
            state=state,
            metadata=metadata,
            workbook=None,
            sheet=sheet,
            table=table,
            input_file_name=input_file_name,
            logger=self.logger,
        )
        if maybe_table is not None:
            table = maybe_table

        table = apply_transforms(
            table=table,
            registry=self.registry,
            settings=self.settings,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        maybe_table = self.registry.run_hooks(
            HookName.ON_TABLE_TRANSFORMED,
            settings=self.settings,
            state=state,
            metadata=metadata,
            workbook=None,
            sheet=sheet,
            table=table,
            input_file_name=input_file_name,
            logger=self.logger,
        )
        if maybe_table is not None:
            table = maybe_table

        table = apply_validators(
            table=table,
            registry=self.registry,
            settings=self.settings,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        maybe_table = self.registry.run_hooks(
            HookName.ON_TABLE_VALIDATED,
            settings=self.settings,
            state=state,
            metadata=metadata,
            workbook=None,
            sheet=sheet,
            table=table,
            input_file_name=input_file_name,
            logger=self.logger,
        )
        if maybe_table is not None:
            table = maybe_table

        table_result = TableResult(
            sheet_name=sheet.title,
            table=table,
            header_row_index=region.header_row_index,
            source_columns=source_cols,
            table_index=table_index,
            sheet_index=int(metadata.get("sheet_index", 0)) if isinstance(metadata, dict) else 0,
            region=region_info,
            mapped_columns=mapped_cols,
            unmapped_columns=unmapped_cols,
            column_scores=scores_by_column,
            duplicate_unmapped_indices=set(duplicate_unmapped_indices),
            row_count=table.height,
        )

        write_table = render_table(
            table_result=table_result,
            writer=writer,
            registry=self.registry,
            settings=self.settings,
            logger=self.logger,
        )

        if self.report_builder is not None:
            try:
                self.report_builder.record_table(table_result)
            except Exception:
                self.logger.exception("Failed to record table summary for engine.run.completed")

        # Hook after write
        self.registry.run_hooks(
            HookName.ON_TABLE_WRITTEN,
            settings=self.settings,
            state=state,
            metadata=metadata,
            workbook=writer.worksheet.parent,
            sheet=writer.worksheet,
            table=table,
            write_table=write_table,
            input_file_name=input_file_name,
            logger=self.logger,
        )
        return table_result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _materialize_rows(self, sheet: Worksheet) -> List[List[Any]]:
        rows, _scan = self._materialize_rows_with_scan(sheet)
        return rows

    def _materialize_rows_with_scan(self, sheet: Worksheet) -> tuple[List[List[Any]], dict[str, Any]]:
        """Stream rows, trim width, and stop after long empty runs."""

        rows: List[List[Any]] = []
        empty_row_run = 0
        max_empty_rows = self.settings.max_empty_rows_run
        max_empty_cols = self.settings.max_empty_cols_run
        row_limit_hit = False

        for row_index, row in enumerate(sheet.iter_rows(values_only=True)):
            last_value_idx = -1
            empty_col_run = 0
            truncated_cols = False

            for idx, cell in enumerate(row):
                if cell not in (None, ""):
                    last_value_idx = idx
                    empty_col_run = 0
                else:
                    empty_col_run += 1
                    if (
                        max_empty_cols is not None
                        and last_value_idx >= 0
                        and empty_col_run >= max_empty_cols
                    ):
                        truncated_cols = True
                        break

            if truncated_cols:
                self.logger.warning(
                    "Truncated row after long empty column run",
                    extra={
                        "data": {
                            "sheet_name": sheet.title,
                            "row_index": row_index,
                            "max_empty_cols_run": max_empty_cols,
                        }
                    },
                )

            if last_value_idx == -1:
                empty_row_run += 1
                if max_empty_rows is not None and empty_row_run >= max_empty_rows:
                    row_limit_hit = True
                    break
                rows.append([])
                continue

            empty_row_run = 0
            trimmed = list(row[: last_value_idx + 1])
            rows.append(trimmed)

        if row_limit_hit:
            self.logger.warning(
                "Stopped scanning sheet after long empty row run",
                extra={
                    "data": {
                        "sheet_name": sheet.title,
                        "rows_emitted": len(rows),
                        "max_empty_rows_run": max_empty_rows,
                    }
                },
            )

        truncated_rows = 0
        if row_limit_hit:
            try:
                truncated_rows = max(0, int(sheet.max_row or 0) - len(rows))
            except Exception:
                truncated_rows = 0

        scan = {
            "rows_emitted": len(rows),
            "stopped_early": bool(row_limit_hit),
            "truncated_rows": int(truncated_rows) if row_limit_hit else 0,
        }
        return rows, scan


__all__ = ["Pipeline"]

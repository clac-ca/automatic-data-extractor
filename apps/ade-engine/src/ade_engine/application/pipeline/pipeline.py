from __future__ import annotations

from typing import Any, List

from openpyxl.worksheet.worksheet import Worksheet

from ade_engine.application.pipeline.detect_columns import build_source_columns, detect_and_map_columns
from ade_engine.application.pipeline.detect_rows import TableRegion, detect_table_regions
from ade_engine.application.pipeline.render import SheetWriter, render_table
from ade_engine.application.pipeline.transform import apply_transforms
from ade_engine.application.pipeline.validate import apply_validators, flatten_issues_patch
from ade_engine.extensions.registry import Registry
from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.infrastructure.settings import Settings
from ade_engine.models.extension_contexts import HookName
from ade_engine.models.table import TableData, TableRegionInfo


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
    ) -> list[TableData]:
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
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        tables: list[TableData] = []
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
    ) -> TableData:
        header_row = rows[region.header_row_index] if region.header_row_index < len(rows) else []
        data_rows = rows[region.data_start_row_index:region.data_end_row_index]

        source_cols = build_source_columns(header_row, data_rows)
        mapped_cols, unmapped_cols, scores_by_column, duplicate_unmapped_indices = detect_and_map_columns(
            sheet_name=sheet.title,
            source_columns=source_cols,
            registry=self.registry,
            settings=self.settings,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        table = TableData(
            sheet_name=sheet.title,
            header_row_index=region.header_row_index,
            source_columns=source_cols,
            table_index=table_index,
            sheet_index=int(metadata.get("sheet_index", 0)) if isinstance(metadata, dict) else 0,
            region=TableRegionInfo(
                header_row_index=region.header_row_index,
                data_start_row_index=region.data_start_row_index,
                data_end_row_index=region.data_end_row_index,
                header_inferred=region.header_inferred,
            ),
            mapped_columns=mapped_cols,
            unmapped_columns=unmapped_cols,
            column_scores=scores_by_column,
            duplicate_unmapped_indices=set(duplicate_unmapped_indices),
        )

        # Hook: table detected
        self.registry.run_hooks(
            HookName.ON_TABLE_DETECTED,
            state=state,
            metadata=metadata,
            workbook=None,
            sheet=sheet,
            table=table,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        # Hook: allow mapping reorder/patch
        self.registry.run_hooks(
            HookName.ON_TABLE_MAPPED,
            state=state,
            metadata=metadata,
            workbook=None,
            sheet=sheet,
            table=table,
            input_file_name=input_file_name,
            logger=self.logger,
        )

        row_count = len(data_rows)
        table.row_count = row_count
        table.columns = {col.field_name: list(col.values) for col in table.mapped_columns}
        table.mapping = {col.field_name: col.source_index for col in table.mapped_columns}

        transform_patch = apply_transforms(
            mapped_columns=table.mapped_columns,
            columns=table.columns,
            mapping=table.mapping,
            registry=self.registry,
            settings=self.settings,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
            row_count=row_count,
        )
        table.issues_patch = transform_patch.issues

        issues_patch = apply_validators(
            mapped_columns=table.mapped_columns,
            columns=table.columns,
            mapping=table.mapping,
            registry=self.registry,
            state=state,
            metadata=metadata,
            input_file_name=input_file_name,
            logger=self.logger,
            row_count=row_count,
            initial_issues=transform_patch.issues,
        )
        table.issues_patch = issues_patch
        table.issues = flatten_issues_patch(
            issues_patch=issues_patch,
            columns=table.columns,
            mapping=table.mapping,
        )

        mapped_fields = [col.field_name for col in table.mapped_columns]
        derived_fields: list[str] = []
        if self.settings.render_derived_fields:
            mapped_set = set(mapped_fields)
            for field in self.registry.fields.keys():
                if field in mapped_set:
                    continue
                if field in table.columns:
                    derived_fields.append(field)
        field_order = [*mapped_fields, *derived_fields]

        render_table(
            table=table,
            writer=writer,
            settings=self.settings,
            field_order=field_order,
            logger=self.logger,
        )

        if self.report_builder is not None:
            try:
                self.report_builder.record_table(table)
            except Exception:
                self.logger.exception("Failed to record table summary for engine.run.completed")

        # Hook after write
        self.registry.run_hooks(
            HookName.ON_TABLE_WRITTEN,
            state=state,
            metadata=metadata,
            workbook=writer.worksheet.parent,
            sheet=writer.worksheet,
            table=table,
            input_file_name=input_file_name,
            logger=self.logger,
        )
        return table

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

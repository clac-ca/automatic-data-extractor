"""Registry container for config callables."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Sequence

import polars as pl
from pydantic import ValidationError

from ade_engine.infrastructure.observability.logger import RunLogger
from ade_engine.models.errors import ConfigError, HookError, PipelineError
from ade_engine.models.extension_contexts import (
    FieldDef,
    HookName,
    ScorePatch,
    SheetEndHookContext,
    SheetStartHookContext,
    TableMappedHookContext,
    TableTransformedHookContext,
    TableValidatedHookContext,
    TableWrittenHookContext,
    WorkbookBeforeSaveHookContext,
    WorkbookStartHookContext,
)
from ade_engine.models.extension_outputs import ColumnDetectorResult, RowDetectorResult
from ade_engine.models.table import TableRegion, TableResult
from ade_engine.extensions.invoke import call_extension

@dataclass
class RegisteredFn:
    fn: Callable[..., Any]
    priority: int
    module: str
    qualname: str
    field: str | None = None
    row_kind: str | None = None
    hook_name: HookName | None = None


class Registry:
    """Holds registered fields, detectors, transforms, validators, and hooks."""

    def __init__(self) -> None:
        self.fields: Dict[str, FieldDef] = {}
        self.row_detectors: List[RegisteredFn] = []
        self.column_detectors: List[RegisteredFn] = []
        self.column_transforms: List[RegisteredFn] = []
        self.column_validators: List[RegisteredFn] = []
        self.column_transforms_by_field: Dict[str, List[RegisteredFn]] = {}
        self.column_validators_by_field: Dict[str, List[RegisteredFn]] = {}
        self.hooks: Dict[HookName, List[RegisteredFn]] = {name: [] for name in HookName}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sort_key(self, item: RegisteredFn):
        return (-item.priority, item.module, item.qualname)

    def _group_by_field(self, items: List[RegisteredFn]) -> Dict[str, List[RegisteredFn]]:
        grouped: Dict[str, List[RegisteredFn]] = {}
        for item in items:
            if item.field is None:
                continue
            grouped.setdefault(item.field, []).append(item)
        return grouped

    def finalize(self) -> None:
        self.row_detectors.sort(key=self._sort_key)
        self.column_detectors.sort(key=self._sort_key)
        self.column_transforms.sort(key=self._sort_key)
        self.column_validators.sort(key=self._sort_key)
        self.column_transforms_by_field = self._group_by_field(self.column_transforms)
        self.column_validators_by_field = self._group_by_field(self.column_validators)
        for hook_list in self.hooks.values():
            hook_list.sort(key=self._sort_key)

    def run_hooks(
        self,
        hook_name: HookName,
        *,
        settings,
        state: dict,
        metadata: Mapping[str, Any],
        logger: RunLogger,
        input_file_name: str,
        source_workbook=None,
        output_workbook=None,
        source_sheet=None,
        output_sheet=None,
        table: pl.DataFrame | None = None,
        write_table: pl.DataFrame | None = None,
        source_region: TableRegion | None = None,
        output_region: TableRegion | None = None,
        table_index: int | None = None,
        table_result: TableResult | None = None,
        tables: Sequence[TableResult] | None = None,
    ) -> pl.DataFrame | None:
        hooks = self.hooks.get(hook_name, [])
        table_returning = hook_name in {
            HookName.ON_TABLE_MAPPED,
            HookName.ON_TABLE_TRANSFORMED,
            HookName.ON_TABLE_VALIDATED,
        }
        if not hooks:
            return table if table_returning else None

        hook_stage = hook_name.value if hasattr(hook_name, "value") else str(hook_name)
        current_table = table
        for hook_def in hooks:
            table_region_ref = None
            sheet_name = None

            if hook_name == HookName.ON_WORKBOOK_START:
                if source_workbook is None:
                    raise HookError("on_workbook_start requires source_workbook", stage=hook_stage)
                ctx = WorkbookStartHookContext(
                    source_workbook=source_workbook,
                    settings=settings,
                    metadata=metadata,
                    state=state,
                    input_file_name=input_file_name,
                    logger=logger,
                )
            elif hook_name == HookName.ON_SHEET_START:
                if source_workbook is None:
                    raise HookError("on_sheet_start requires source_workbook", stage=hook_stage)
                if source_sheet is None:
                    raise HookError("on_sheet_start requires source_sheet", stage=hook_stage)
                ctx = SheetStartHookContext(
                    source_sheet=source_sheet,
                    source_workbook=source_workbook,
                    settings=settings,
                    metadata=metadata,
                    state=state,
                    input_file_name=input_file_name,
                    logger=logger,
                )
                sheet_name = getattr(source_sheet, "title", None)
            elif hook_name == HookName.ON_SHEET_END:
                if output_workbook is None:
                    raise HookError("on_sheet_end requires output_workbook", stage=hook_stage)
                if output_sheet is None:
                    raise HookError("on_sheet_end requires output_sheet", stage=hook_stage)
                if tables is None:
                    raise HookError("on_sheet_end requires tables", stage=hook_stage)
                ctx = SheetEndHookContext(
                    output_sheet=output_sheet,
                    output_workbook=output_workbook,
                    tables=tables,
                    settings=settings,
                    metadata=metadata,
                    state=state,
                    input_file_name=input_file_name,
                    logger=logger,
                )
                sheet_name = getattr(output_sheet, "title", None)
            elif hook_name in {
                HookName.ON_TABLE_MAPPED,
                HookName.ON_TABLE_TRANSFORMED,
                HookName.ON_TABLE_VALIDATED,
            }:
                if source_workbook is None:
                    raise HookError(f"{hook_stage} requires source_workbook", stage=hook_stage)
                if source_sheet is None:
                    raise HookError(f"{hook_stage} requires source_sheet", stage=hook_stage)
                if current_table is None:
                    raise HookError(f"{hook_stage} requires table", stage=hook_stage)
                if source_region is None:
                    raise HookError(f"{hook_stage} requires source_region", stage=hook_stage)
                if table_index is None:
                    raise HookError(f"{hook_stage} requires table_index", stage=hook_stage)

                table_region_ref = source_region.a1 if isinstance(source_region, TableRegion) else None
                sheet_name = getattr(source_sheet, "title", None)

                if hook_name == HookName.ON_TABLE_MAPPED:
                    ctx = TableMappedHookContext(
                        table=current_table,
                        source_sheet=source_sheet,
                        source_workbook=source_workbook,
                        source_region=source_region,
                        table_index=table_index,
                        settings=settings,
                        metadata=metadata,
                        state=state,
                        input_file_name=input_file_name,
                        logger=logger,
                    )
                elif hook_name == HookName.ON_TABLE_TRANSFORMED:
                    ctx = TableTransformedHookContext(
                        table=current_table,
                        source_sheet=source_sheet,
                        source_workbook=source_workbook,
                        source_region=source_region,
                        table_index=table_index,
                        settings=settings,
                        metadata=metadata,
                        state=state,
                        input_file_name=input_file_name,
                        logger=logger,
                    )
                else:
                    ctx = TableValidatedHookContext(
                        table=current_table,
                        source_sheet=source_sheet,
                        source_workbook=source_workbook,
                        source_region=source_region,
                        table_index=table_index,
                        settings=settings,
                        metadata=metadata,
                        state=state,
                        input_file_name=input_file_name,
                        logger=logger,
                    )
            elif hook_name == HookName.ON_TABLE_WRITTEN:
                if output_workbook is None:
                    raise HookError(f"{hook_stage} requires output_workbook", stage=hook_stage)
                if output_sheet is None:
                    raise HookError(f"{hook_stage} requires output_sheet", stage=hook_stage)
                if write_table is None:
                    raise HookError(f"{hook_stage} requires write_table", stage=hook_stage)
                if output_region is None:
                    raise HookError(f"{hook_stage} requires output_region", stage=hook_stage)
                if table_index is None:
                    raise HookError(f"{hook_stage} requires table_index", stage=hook_stage)
                if table_result is None:
                    raise HookError(f"{hook_stage} requires table_result", stage=hook_stage)

                table_region_ref = output_region.a1 if isinstance(output_region, TableRegion) else None
                sheet_name = getattr(output_sheet, "title", None)

                ctx = TableWrittenHookContext(
                    write_table=write_table,
                    output_sheet=output_sheet,
                    output_workbook=output_workbook,
                    output_region=output_region,
                    table_index=table_index,
                    table_result=table_result,
                    settings=settings,
                    metadata=metadata,
                    state=state,
                    input_file_name=input_file_name,
                    logger=logger,
                )
            elif hook_name == HookName.ON_WORKBOOK_BEFORE_SAVE:
                if output_workbook is None:
                    raise HookError("on_workbook_before_save requires output_workbook", stage=hook_stage)
                ctx = WorkbookBeforeSaveHookContext(
                    output_workbook=output_workbook,
                    settings=settings,
                    metadata=metadata,
                    state=state,
                    input_file_name=input_file_name,
                    logger=logger,
                )
            else:  # pragma: no cover - defensive
                raise HookError(f"Unsupported hook: {hook_stage}", stage=hook_stage)

            logger.event(
                "hook.start",
                level=logging.DEBUG,
                data={
                    "hook_name": hook_stage,
                    "hook": hook_def.qualname,
                    "table_index": table_index,
                    "table_region": table_region_ref,
                    "sheet_name": sheet_name,
                },
            )
            try:
                out = call_extension(hook_def.fn, ctx, label=f"Hook {hook_def.qualname}")
            except Exception as exc:
                message = f"Hook {hook_def.qualname} failed during {hook_stage}"
                logger.exception(message, exc_info=exc)
                raise HookError(message, stage=hook_stage) from exc

            if table_returning:
                if out is None:
                    pass
                elif isinstance(out, pl.DataFrame):
                    current_table = out
                else:
                    message = (
                        f"Hook {hook_def.qualname} must return a polars DataFrame or None during {hook_stage}"
                    )
                    raise HookError(message, stage=hook_stage)
            elif out is not None:
                message = f"Hook {hook_def.qualname} must return None during {hook_stage}"
                raise HookError(message, stage=hook_stage)
            logger.event(
                "hook.end",
                level=logging.DEBUG,
                data={
                    "hook_name": hook_stage,
                    "hook": hook_def.qualname,
                    "table_index": table_index,
                    "table_region": table_region_ref,
                    "sheet_name": sheet_name,
                },
            )
        return current_table if table_returning else None

    # ------------------------------------------------------------------
    # Field registration
    # ------------------------------------------------------------------
    def register_field(self, field_def: FieldDef) -> FieldDef:
        if field_def.name in self.fields:
            raise ConfigError(f"Field '{field_def.name}' already registered")
        self.fields[field_def.name] = field_def
        return field_def

    def _require_field(self, name: str) -> FieldDef:
        field = self.fields.get(name)
        if field is None:
            raise ConfigError(f"Field '{name}' must be registered before registering detectors/transforms/validators")
        return field

    # ------------------------------------------------------------------
    # Score validation
    # ------------------------------------------------------------------
    def validate_detector_scores(
        self,
        patch: ScorePatch,
        *,
        allow_unknown: bool = False,
        source: str | None = None,
        model: type[RowDetectorResult] | type[ColumnDetectorResult] = ColumnDetectorResult,
    ) -> dict[str, float]:
        """Validate detector output to a strict score map."""

        source_name = source or "detector"
        if patch is None:
            return {}
        try:
            validated = model.model_validate(patch)
        except ValidationError as exc:
            raise PipelineError(
                f"{source_name} must return a dict[str, float] or None ({exc})"
            ) from exc

        scores = dict(validated.scores)
        if not allow_unknown:
            unknown_fields = [field for field in scores if field not in self.fields]
            if unknown_fields:
                unknown = ", ".join(sorted(unknown_fields))
                raise PipelineError(f"{source_name} returned unknown field(s): {unknown}")

        return scores

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def register_row_detector(self, fn: Callable[..., Any], *, row_kind: str, priority: int) -> None:
        self.row_detectors.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                row_kind=row_kind,
            )
        )

    def register_column_detector(self, fn: Callable[..., Any], *, field: str, priority: int) -> None:
        self._require_field(field)
        self.column_detectors.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                field=field,
            )
        )

    def register_column_transform(self, fn: Callable[..., Any], *, field: str, priority: int) -> None:
        self._require_field(field)
        self.column_transforms.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                field=field,
            )
        )

    def register_column_validator(self, fn: Callable[..., Any], *, field: str, priority: int) -> None:
        self._require_field(field)
        self.column_validators.append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                field=field,
            )
        )

    def register_hook(self, fn: Callable[..., Any], *, hook: str, priority: int) -> None:
        try:
            hook_name = HookName(hook)
        except ValueError as exc:
            valid = ", ".join(sorted(name.value for name in HookName))
            raise ConfigError(f"Unknown hook '{hook}'. Must be one of: {valid}") from exc

        self.hooks[hook_name].append(
            RegisteredFn(
                fn=fn,
                priority=priority,
                module=getattr(fn, "__module__", ""),
                qualname=getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>")),
                hook_name=hook_name,
            )
        )


__all__ = ["Registry", "RegisteredFn"]

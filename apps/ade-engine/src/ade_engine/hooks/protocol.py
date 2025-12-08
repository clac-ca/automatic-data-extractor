"""Hook protocol describing the lifecycle callbacks."""

from __future__ import annotations

from typing import Optional, Protocol

from ade_engine.types.contexts import RunContext, TableContext, WorksheetContext
from ade_engine.types.mapping import ColumnMappingPatch


class ADEHooks(Protocol):
    def on_workbook_start(self, ctx: RunContext) -> None: ...
    def on_sheet_start(self, sheet_ctx: WorksheetContext) -> None: ...
    def on_table_detected(self, table_ctx: TableContext) -> None: ...
    def on_table_mapped(self, table_ctx: TableContext) -> Optional[ColumnMappingPatch]: ...
    def on_table_written(self, table_ctx: TableContext) -> None: ...
    def on_workbook_before_save(self, ctx: RunContext) -> None: ...


__all__ = ["ADEHooks"]

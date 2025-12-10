"""No-op hook implementations for convenience/testing."""

from __future__ import annotations

from ade_engine.types.contexts import RunContext, TableContext, WorksheetContext
from ade_engine.types.mapping import ColumnMappingPatch


class BaseHooks:
    """Default hook implementation that does nothing."""

    def on_workbook_start(self, ctx: RunContext) -> None:  # noqa: ARG002
        return None

    def on_sheet_start(self, sheet_ctx: WorksheetContext) -> None:  # noqa: ARG002
        return None

    def on_table_detected(self, table_ctx: TableContext) -> None:  # noqa: ARG002
        return None

    def on_table_mapped(self, table_ctx: TableContext) -> ColumnMappingPatch | None:  # noqa: ARG002
        return None

    def on_table_written(self, table_ctx: TableContext) -> None:  # noqa: ARG002
        return None

    def on_workbook_before_save(self, ctx: RunContext) -> None:  # noqa: ARG002
        return None


__all__ = ["BaseHooks"]

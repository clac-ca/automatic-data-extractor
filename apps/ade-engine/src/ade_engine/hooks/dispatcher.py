"""Fanout dispatcher for manifest-defined hooks."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from ade_engine.config.hooks import HooksRuntime
from ade_engine.exceptions import HookError
from ade_engine.hooks.base import BaseHooks
from ade_engine.runtime import PluginInvoker
from ade_engine.types.contexts import RunContext, TableContext, WorksheetContext
from ade_engine.types.mapping import ColumnMappingPatch


def _hook_name(hook: Any) -> str:
    name = getattr(hook, "__name__", None) or hook.__class__.__name__
    module = getattr(hook, "__module__", None)
    return f"{module}.{name}" if module else str(name)


class HookDispatcher(BaseHooks):
    """Invokes configured hook modules in order for each stage."""

    def __init__(
        self,
        hooks: HooksRuntime | None,
        *,
        invoker: PluginInvoker,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.hooks = hooks or HooksRuntime()
        self.invoker = invoker
        self.logger = logger or logging.getLogger(__name__)

    def _invoke(self, stage_name: str, callables: Iterable[Any], **kwargs: Any) -> list[Any]:
        results: list[Any] = []
        for hook in callables:
            try:
                results.append(self.invoker.call(hook, **kwargs))
            except Exception as exc:
                self.logger.exception("Hook failed during %s", stage_name, exc_info=exc)
                raise HookError(f"Hook {_hook_name(hook)} failed during {stage_name}") from exc

        return results

    @staticmethod
    def _table_kwargs(table_ctx: TableContext) -> dict[str, Any]:
        return {
            "table_ctx": table_ctx,
            "sheet_ctx": table_ctx.sheet,
            "run_ctx": table_ctx.sheet.run,
        }

    def on_workbook_start(self, ctx: RunContext) -> None:
        self._invoke("on_workbook_start", self.hooks.on_workbook_start, run_ctx=ctx)

    def on_sheet_start(self, sheet_ctx: WorksheetContext) -> None:
        self._invoke("on_sheet_start", self.hooks.on_sheet_start, sheet_ctx=sheet_ctx, run_ctx=sheet_ctx.run)

    def on_table_detected(self, table_ctx: TableContext) -> None:
        self._invoke("on_table_detected", self.hooks.on_table_detected, **self._table_kwargs(table_ctx))

    def on_table_mapped(self, table_ctx: TableContext) -> ColumnMappingPatch | None:
        results = self._invoke("on_table_mapped", self.hooks.on_table_mapped, **self._table_kwargs(table_ctx))
        return next((candidate for candidate in reversed(results) if candidate), None)

    def on_table_written(self, table_ctx: TableContext) -> None:
        self._invoke("on_table_written", self.hooks.on_table_written, **self._table_kwargs(table_ctx))

    def on_workbook_before_save(self, ctx: RunContext) -> None:
        self._invoke("on_workbook_before_save", self.hooks.on_workbook_before_save, run_ctx=ctx)


__all__ = ["HookDispatcher"]

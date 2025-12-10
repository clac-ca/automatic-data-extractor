from __future__ import annotations

from typing import Any

from ade_engine.registry import HookContext, HookName, hook


@hook(HookName.ON_TABLE_MAPPED)
def on_table_mapped(ctx: HookContext):
    """Optional mapping patch hook.

    Return a ColumnMappingPatch (or None). This is the place to:
      - call an LLM with the extracted headers
      - propose a patch for unmapped/incorrect fields
      - rename/drop passthrough columns

    This template returns None by default.
    """

    if ctx.logger and ctx.table:
        mapped_fields = [col.field_name for col in getattr(ctx.table, "mapped_columns", [])]
        ctx.logger.info("Config hook: table mapped (fields=%s)", mapped_fields)
    return None

from __future__ import annotations

from typing import Any

from ade_engine.registry import hook


@hook("on_table_mapped")
def run(*, table_ctx: Any, sheet_ctx: Any, run_ctx: Any, logger: Any | None = None, **_: Any):
    """Optional mapping patch hook.

    Return a ColumnMappingPatch (or None). This is the place to:
      - call an LLM with the extracted headers
      - propose a patch for unmapped/incorrect fields
      - rename/drop passthrough columns

    This template returns None by default.
    """
    if logger:
        logger.info("Config hook: table mapped (mapping is available on table_ctx.mapping)")
    return None

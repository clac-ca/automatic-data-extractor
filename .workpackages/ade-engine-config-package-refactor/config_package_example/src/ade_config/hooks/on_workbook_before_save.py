from __future__ import annotations

from typing import Any

from ade_engine.registry import hook


@hook("on_workbook_before_save")
def run(*, run_ctx: Any, logger: Any | None = None, **_: Any) -> None:
    # Example: final workbook-level formatting, cover sheets, metadata, etc.
    if logger:
        logger.info("Config hook: workbook before save (%s)", getattr(run_ctx, "output_path", ""))

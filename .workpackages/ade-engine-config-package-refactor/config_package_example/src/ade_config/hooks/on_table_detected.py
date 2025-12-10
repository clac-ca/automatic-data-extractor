from __future__ import annotations

from typing import Any

from ade_engine.registry import hook


@hook("on_table_detected")
def run(*, table_ctx: Any, sheet_ctx: Any, run_ctx: Any, logger: Any | None = None, **_: Any) -> None:
    # Example: log the detected region.
    origin = getattr(table_ctx, "origin", None)
    if logger:
        logger.info("Config hook: table detected (origin=%s)", origin)

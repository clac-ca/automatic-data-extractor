"""on_after_extract hook.

Runs after RawTable objects have been built, before column mapping.
"""

from __future__ import annotations

from typing import Any


def run(ctx: Any) -> None:
    """Log how many tables were detected."""
    logger = getattr(ctx, "logger", None)
    tables = getattr(ctx, "tables", None) or []

    if logger is None:
        return

    logger.note(
        "Finished extract phase",
        stage=getattr(ctx, "stage", None),
        table_count=len(tables),
    )

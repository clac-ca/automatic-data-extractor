"""
ADE hook: ``on_sheet_end``.

This hook runs once per worksheet after ADE has finished writing all normalized
output tables into the *output* workbook/worksheet. Use it for sheet-level
formatting, summaries, or post-processing that needs the final written state.

Contract
--------
- Called once per output worksheet.
- Must return ``None`` (any other return value is an error).

Guidance
--------
- Prefer deterministic, idempotent formatting operations.
- Avoid heavy scans; reuse facts captured earlier in ``state``.
- Keep data edits earlier in the pipeline (mapped/transformed/validated).
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    import openpyxl
    import openpyxl.worksheet.worksheet

    from ade_engine.extensions.registry import Registry
    from ade_engine.infrastructure.observability.logger import RunLogger
    from ade_engine.infrastructure.settings import Settings


def register(registry: Registry) -> None:
    """Register hook(s) with the ADE registry."""
    registry.register_hook(on_sheet_end, hook="on_sheet_end", priority=0)

    # ---------------------------------------------------------------------
    # Examples (uncomment to enable, then customize as needed)
    # ---------------------------------------------------------------------
    # registry.register_hook(on_sheet_end_example_1_record_output_bounds, hook="on_sheet_end", priority=10)


def on_sheet_end(
    *,
    sheet: openpyxl.worksheet.worksheet.Worksheet,  # Output worksheet (openpyxl Worksheet)
    workbook: openpyxl.Workbook,  # Output workbook (openpyxl Workbook)
    input_file_name: str,  # Input filename (basename)
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> None:  # noqa: ARG001
    """Default implementation is a placeholder (no-op)."""
    return None


# ----------------------------
# Examples (uncomment in register() to enable)
# ----------------------------


def on_sheet_end_example_1_record_output_bounds(
    *,
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    workbook: openpyxl.Workbook,
    input_file_name: str,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    logger: RunLogger,
) -> None:  # noqa: ARG001
    """Example: record output bounds for the sheet and log a short summary."""
    sheet_name = str(getattr(sheet, "title", ""))
    bounds = {
        "max_row": int(sheet.max_row or 0),
        "max_col": int(sheet.max_column or 0),
        "dimension": sheet.calculate_dimension() if hasattr(sheet, "calculate_dimension") else None,
    }

    stats = state.get("sheet_output_bounds")
    if not isinstance(stats, dict):
        stats = {}
        state["sheet_output_bounds"] = stats
    stats[sheet_name] = bounds

    if logger:
        logger.info(
            "Sheet output bounds recorded",
            extra={"data": {"sheet_name": sheet_name, **bounds}},
        )

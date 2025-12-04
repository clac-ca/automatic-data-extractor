"""
Example: `on_after_extract` hook

This hook runs AFTER the extraction phase (where ExtractedTable objects
have been created) but BEFORE column mapping.

Purpose:
    • Inspect, reorder, drop, or modify ExtractedTable objects
    • Validate table metadata
    • Normalize table structures
    • Emit custom logs or events

The engine passes a list of ExtractedTable objects as `tables` and will use
WHATEVER list you return for downstream processing.

Return options:
    • Return a new list → mapping stage receives your modified list
    • Return None      → preserve original list (you may mutate in place)
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    tables: list[Any] | None = None,  # typically List[ExtractedTable]
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    file_names: tuple[str, ...] | None = None,
    manifest: Any | None = None,
    logger=None,
    event_emitter=None,
    stage: Any | None = None,
    **_: Any,
) -> list[Any] | None:
    """
    Main entrypoint for the `on_after_extract` hook.

    Recommended use cases:
      • Drop empty or useless tables
      • Merge tables detected from the same source
      • Enforce naming conventions
      • Record metrics or emit events
    """

    if tables is None:
        # Returning None tells the engine: "use whatever you gave me"
        return None

    logger and logger.info("on_after_extract: %d tables extracted", len(tables))

    # -----------------------------------------------------------------------
    # EXAMPLE: Drop empty tables
    # -----------------------------------------------------------------------
    # Many spreadsheets include placeholder tabs or formatting-only sheets.
    #
    # We filter out tables that have no data rows. This is a common pattern
    # and highlights how hooks can transform the table list.
    # -----------------------------------------------------------------------

    filtered: list[Any] = []

    for table in tables:
        data_rows = getattr(table, "data_rows", None) or []

        if data_rows:
            # Keep non-empty tables
            filtered.append(table)
            continue

        # Log dropped table metadata for debugging
        logger and logger.info(
            "Dropping empty table: file=%s sheet=%s",
            getattr(table, "source_file", "<unknown>"),
            getattr(table, "source_sheet", None),
        )

    # Returning a list replaces the original table list for the mapping stage.
    return filtered

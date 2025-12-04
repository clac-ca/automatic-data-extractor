"""
Example: `on_after_mapping` hook

This hook runs AFTER MappedTable objects have been produced
(field-level mapping is complete) but BEFORE normalization.

Purpose:
    • Inspect mapped tables
    • Enrich or modify metadata
    • Drop or reorder tables
    • Emit validation logs or events
    • Fix common issues before normalization begins

The engine passes a list of MappedTable objects as `tables`. You may:

    • Return a modified list → mapping stage output is replaced
    • Return None           → engine keeps the original list
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# HOOK ENTRYPOINT
# ---------------------------------------------------------------------------

def run(
    *,
    tables: list[Any] | None = None,   # typically List[MappedTable]
    run: Any | None = None,
    state: dict[str, Any] | None = None,
    input_file_name: str | None = None,
    manifest: Any | None = None,
    logger=None,
    event_emitter=None,
    stage: Any | None = None,
    **_: Any,
) -> list[Any] | None:
    """
    Main entrypoint for the `on_after_mapping` hook.

    Typical use cases:
      • Log or validate mapping completeness
      • Drop tables with zero mapped fields
      • Enrich table metadata before normalization
      • Flag suspicious patterns for debugging
      • Convert extras → metadata or warnings

    Returning:
      • list of MappedTable: modifies the pipeline output
      • None: keep the original list (optionally mutated)
    """

    if tables is None:
        return None

    # If logger is missing, we fall back to returning original tables.
    if logger is None:
        return tables

    logger.info("on_after_mapping: inspecting %d mapped tables", len(tables))

    # -----------------------------------------------------------------------
    # EXAMPLE: Log mapping summary + emit events
    # -----------------------------------------------------------------------

    for mapped_table in tables:
        extracted = getattr(mapped_table, "extracted", None)
        source_file = getattr(getattr(extracted, "source_file", None), "name", None)
        source_sheet = getattr(extracted, "source_sheet", None)

        mapping = getattr(mapped_table, "mapping", []) or []
        extras = getattr(mapped_table, "extras", []) or []

        logger.info(
            "MappedTable summary: file=%s sheet=%s mapped=%s extras=%s",
            source_file,
            source_sheet,
            len(mapping),
            len(extras),
        )
        
    # -----------------------------------------------------------------------
    # EXAMPLE: No structural changes — return original tables
    # -----------------------------------------------------------------------
    # This example only inspects/logs metadata. You may replace this with:
    #   • filtering
    #   • reordering
    #   • metadata injection
    #   • error handling
    # -----------------------------------------------------------------------

    return tables

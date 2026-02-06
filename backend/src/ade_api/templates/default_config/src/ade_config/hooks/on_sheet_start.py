"""
ADE hook: ``on_sheet_start``.

This hook runs once per worksheet, after the workbook has been opened and before ADE
performs table detection. It is the earliest per-sheet entrypoint.

Use this hook to make cheap, sheet-scoped decisions and to seed context for downstream
detectors/transforms/validators (e.g., skip/routing flags, header/data-row hints, sheet
metadata, structured logs/events).

Contract
--------
- Called once per worksheet.
- Must return ``None`` (any other return value is an error).

Guidance
--------
- Keep work inexpensive and deterministic (avoid scanning large cell ranges).
- Avoid mutating the workbook/worksheet.
- Prefer storing derived facts under a per-sheet namespace in ``state`` and emitting
  structured events via the provided logger.
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
    """Register this config package's on_sheet_start hook(s)."""
    registry.register_hook(on_sheet_start, hook="on_sheet_start", priority=0)

    # ---------------------------------------------------------------------
    # Examples (uncomment to enable, then customize as needed)
    # ---------------------------------------------------------------------
    # registry.register_hook(on_sheet_start_example_0_seed_sheet_state_and_log, hook="on_sheet_start", priority=10)
    # registry.register_hook(on_sheet_start_example_1_route_or_skip_sheets, hook="on_sheet_start", priority=20)
    # registry.register_hook(on_sheet_start_example_2_capture_excel_tables, hook="on_sheet_start", priority=30)
    # registry.register_hook(on_sheet_start_example_3_hint_header_from_freeze_panes, hook="on_sheet_start", priority=40)


def on_sheet_start(
    *,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,  # Source worksheet (openpyxl Worksheet)
    source_workbook: openpyxl.Workbook,  # Source workbook (openpyxl Workbook)
    input_file_name: str,  # Input filename (basename)
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> None:  # noqa: ARG001
    """Called once per worksheet, before ADE scans the sheet for tables.

    Default implementation is a placeholder (no-op). Add your own sheet-scoped logic
    here or enable one of the examples in `register()`.
    """
    return None


# ----------------------------
# Examples (uncomment in register() to enable)
# ----------------------------


def on_sheet_start_example_0_seed_sheet_state_and_log(
    *,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,  # Source worksheet (openpyxl Worksheet)
    source_workbook: openpyxl.Workbook,  # Source workbook (openpyxl Workbook)
    input_file_name: str,  # Input filename (basename)
    settings: Settings,  # Engine Settings
    metadata: Mapping[str, Any],  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: MutableMapping[str, Any],  # Mutable dict shared across the run
    logger: RunLogger,  # RunLogger (structured events + text logs)
) -> None:  # noqa: ARG001
    """Example 0 (recommended): seed per-sheet state and log sheet basics.

    - increments a sheet counter
    - creates/stashes a per-sheet state dict (`state["sheets"][sheet_name]`)
    - records lightweight sheet facts that are commonly useful later
    - emits a structured config event for observability
    """
    # `state` is already the shared mutable dict for the run.
    cfg = state

    # --- stats (shared across run)
    stats = cfg.get("stats")
    if not isinstance(stats, dict):
        stats = {}
        cfg["stats"] = stats
    stats["sheets_seen"] = int(stats.get("sheets_seen", 0) or 0) + 1

    # --- sheet facts + per-sheet context dict
    sheet_name = str(getattr(source_sheet, "title", None) or getattr(source_sheet, "name", None) or "")

    sheet_index: int | None = None
    raw_index = metadata.get("sheet_index", None)
    try:
        sheet_index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        sheet_index = None

    sheets = cfg.get("sheets")
    if not isinstance(sheets, dict):
        sheets = {}
        cfg["sheets"] = sheets

    ctx = sheets.get(sheet_name)
    if not isinstance(ctx, dict):
        ctx = {}
        sheets[sheet_name] = ctx

    dimensions: str | None = None
    try:
        dims = getattr(source_sheet, "dimensions", None)
        if dims is not None:
            dimensions = str(dims)
    except Exception:
        dimensions = None

    if dimensions is None:
        try:
            calc = getattr(source_sheet, "calculate_dimension", None)
            if callable(calc):
                dimensions = str(calc())
        except Exception:
            dimensions = None

    # Store cheap, commonly useful sheet facts.
    # Use setdefault so downstream hooks can override intentionally.
    ctx.setdefault("sheet_index", sheet_index)
    ctx.setdefault("sheet_state", getattr(source_sheet, "sheet_state", None))
    ctx.setdefault("dimensions", dimensions)
    ctx.setdefault("max_row", getattr(source_sheet, "max_row", None))
    ctx.setdefault("max_column", getattr(source_sheet, "max_column", None))
    ctx.setdefault("sheet_name_normalized", sheet_name.strip().lower())

    if input_file_name:
        ctx.setdefault("input_file_name", input_file_name)

    # --- logging (keep it structured and cheap)
    if logger:
        logger.info(
            "Config hook: source_sheet start file=%s source_sheet=%s index=%s dims=%s",
            input_file_name or "<unknown>",
            sheet_name,
            sheet_index if sheet_index is not None else "<unknown>",
            ctx.get("dimensions") or "<unknown>",
        )

        logger.event(
            "engine.config.source_sheet.start",
            data={
                "input_file_name": input_file_name,
                "sheet_name": sheet_name,
                "sheet_index": sheet_index,
                "sheet_state": ctx.get("sheet_state"),
                "dimensions": ctx.get("dimensions"),
            },
        )

    return None


def on_sheet_start_example_1_route_or_skip_sheets(
    *,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,
    source_workbook: openpyxl.Workbook,
    input_file_name: str,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    logger: RunLogger,
) -> None:
    """
    Example 1 (high value): route/skip sheets early.

    Real-world Excel workbooks commonly include:
    - hidden/veryHidden sheets
    - cover pages / instructions
    - helper sheets that are not meant to be parsed

    This example sets a per-sheet flag:
        state["sheets"][sheet_name]["skip"] = True
    which your detectors/transforms can consult to avoid scanning/processing.
    """
    sheet_name = str(getattr(source_sheet, "title", None) or getattr(source_sheet, "name", None) or "")

    cfg = state

    sheets = cfg.get("sheets")
    if not isinstance(sheets, dict):
        sheets = {}
        cfg["sheets"] = sheets
    ctx = sheets.get(sheet_name)
    if not isinstance(ctx, dict):
        ctx = {}
        sheets[sheet_name] = ctx

    sheet_state = getattr(source_sheet, "sheet_state", None)
    normalized = sheet_name.strip().lower()

    sheet_index: int | None = None
    raw_index = metadata.get("sheet_index", None)
    try:
        sheet_index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        sheet_index = None

    # Customize these rules for your org's spreadsheets.
    # Keep rules readable and deterministic.
    non_data_names = {"readme", "instructions", "cover", "notes", "info"}
    non_data_prefixes = ("_", "#")

    reason: str | None = None
    if sheet_state in {"hidden", "veryHidden"}:
        reason = f"sheet_state={sheet_state}"
    elif normalized in non_data_names:
        reason = "non-data source_sheet name"
    elif normalized.startswith(non_data_prefixes):
        reason = "non-data source_sheet prefix"

    if not reason:
        return None

    ctx["skip"] = True
    ctx["skip_reason"] = reason

    if logger:
        logger.info("Config hook: skipping source_sheet=%s (%s)", sheet_name, reason)
        logger.event(
            "engine.config.source_sheet.skip",
            data={
                "input_file_name": input_file_name,
                "sheet_name": sheet_name,
                "sheet_index": sheet_index,
                "reason": reason,
            },
        )

    return None


def on_sheet_start_example_2_capture_excel_tables(
    *,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,
    source_workbook: openpyxl.Workbook,
    input_file_name: str,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    logger: RunLogger,
) -> None:
    """
    Example 2 (high value): capture Excel-defined tables (if present).

    Excel "Tables" (Insert → Table) are structured objects with a name and a range.
    openpyxl exposes them via `worksheet.tables` (dict-like).

    Why this matters:
    - If your spreadsheets already define tables, you can use those definitions as
      strong hints (or even as the source of truth) for ADE table detection.
    """
    sheet_name = str(getattr(source_sheet, "title", None) or getattr(source_sheet, "name", None) or "")
    tables = getattr(source_sheet, "tables", None)
    if not tables:
        return None

    extracted: list[dict[str, str | None]] = []
    try:
        for t in tables.values():
            extracted.append(
                {
                    # openpyxl Table can have `.name` and/or `.displayName`
                    "name": getattr(t, "name", None) or getattr(t, "displayName", None),
                    "ref": getattr(t, "ref", None),
                }
            )
    except Exception:
        # Be defensive: if a source_sheet object provides tables in an unexpected shape,
        # prefer silently doing nothing in an example hook.
        return None

    cfg = state

    sheets = cfg.get("sheets")
    if not isinstance(sheets, dict):
        sheets = {}
        cfg["sheets"] = sheets
    ctx = sheets.get(sheet_name)
    if not isinstance(ctx, dict):
        ctx = {}
        sheets[sheet_name] = ctx
    ctx["excel_tables"] = extracted

    sheet_index: int | None = None
    raw_index = metadata.get("sheet_index", None)
    try:
        sheet_index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        sheet_index = None

    if logger:
        logger.event(
            "engine.config.source_sheet.excel_tables",
            data={
                "input_file_name": input_file_name,
                "sheet_name": sheet_name,
                "sheet_index": sheet_index,
                "table_count": len(extracted),
                # Log names/refs only (avoid dumping cell content).
                "tables": [{"name": t.get("name"), "ref": t.get("ref")} for t in extracted],
            },
        )

    return None


def on_sheet_start_example_3_hint_header_from_freeze_panes(
    *,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,
    source_workbook: openpyxl.Workbook,
    input_file_name: str,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: MutableMapping[str, Any],
    logger: RunLogger,
) -> None:
    """
    Example 3 (high value): derive header/data row hints from freeze panes.

    Many "real" spreadsheets freeze header rows. If the freeze_panes top-left cell
    is 'A2', that often means:
      - header rows = 1
      - first data row = 2

    This example stashes a hint that downstream detectors can use to start scanning
    for tables below the header region (without scanning the whole sheet).
    """
    sheet_name = str(getattr(source_sheet, "title", None) or getattr(source_sheet, "name", None) or "")

    fp = getattr(source_sheet, "freeze_panes", None)
    coord = fp if isinstance(fp, str) else getattr(fp, "coordinate", None)
    if not isinstance(coord, str) or not coord:
        return None

    # Parse trailing digits (row number) from a coordinate like "A2" or "B10".
    digits = ""
    for ch in reversed(coord):
        if ch.isdigit():
            digits = ch + digits
        else:
            break

    if not digits:
        return None

    try:
        first_data_row = int(digits)
    except ValueError:
        return None

    if first_data_row <= 1:
        return None

    header_rows = first_data_row - 1

    cfg = state

    sheets = cfg.get("sheets")
    if not isinstance(sheets, dict):
        sheets = {}
        cfg["sheets"] = sheets
    ctx = sheets.get(sheet_name)
    if not isinstance(ctx, dict):
        ctx = {}
        sheets[sheet_name] = ctx

    hints = ctx.get("hints")
    if not isinstance(hints, dict):
        hints = {}
        ctx["hints"] = hints
    hints.setdefault("header_rows", header_rows)
    hints.setdefault("first_data_row", first_data_row)

    sheet_index: int | None = None
    raw_index = metadata.get("sheet_index", None)
    try:
        sheet_index = int(raw_index) if raw_index is not None else None
    except (TypeError, ValueError):
        sheet_index = None

    if logger:
        logger.event(
            "engine.config.source_sheet.hint.freeze_panes",
            data={
                "input_file_name": input_file_name,
                "sheet_name": sheet_name,
                "sheet_index": sheet_index,
                "freeze_panes": getattr(source_sheet, "freeze_panes", None),
                "header_rows": header_rows,
                "first_data_row": first_data_row,
            },
        )

    return None

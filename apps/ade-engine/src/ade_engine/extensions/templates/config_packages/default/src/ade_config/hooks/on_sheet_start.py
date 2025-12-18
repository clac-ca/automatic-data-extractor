from __future__ import annotations


def register(registry):
    registry.register_hook(on_sheet_start, hook="on_sheet_start", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_sheet_start_example_1_seed_per_sheet_state, hook="on_sheet_start", priority=0)
    # registry.register_hook(on_sheet_start_example_2_stash_sheet_properties, hook="on_sheet_start", priority=0)
    # registry.register_hook(on_sheet_start_example_3_enrich_metadata, hook="on_sheet_start", priority=0)
    # registry.register_hook(on_sheet_start_example_4_emit_structured_event, hook="on_sheet_start", priority=0)
    # registry.register_hook(on_sheet_start_example_5_fail_fast_blank_sheet_name, hook="on_sheet_start", priority=0)


def on_sheet_start(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # Source workbook (openpyxl Workbook)
    sheet,  # Source worksheet (openpyxl Worksheet)
    table,  # Always None for this hook
    write_table,  # Always None for this hook
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> None:
    """
    Called once per worksheet, before ADE scans the sheet for tables.

    This is the earliest "per-sheet" hook. It runs after `on_workbook_start` and
    before any table detection/mapping/transforms/validation happen for this
    sheet. At this point `table` is always `None`.

    Common uses:
    - Initialize per-sheet state (counters, hints) in the shared `state` dict
    - Emit sheet-specific logs (useful when batch processing many files)
    - Read sheet properties to drive detectors/transforms later (via `state`)
    - Fail fast for unexpected sheet layouts (raise; the run will fail as HookError)

    Notes:
    - Prefer mutating `state` (not globals) to share data with other hooks and
      detectors in a thread-safe way.
    - If you use `logger.event(...)`, emit under `engine.config.*` (e.g.
      `logger.event("config.my_event", ...)`) so you don't trip strict validation
      for `engine.*` events.
    """

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    if logger:
        logger.info("Config hook: sheet start (%s)", sheet_name)

    return None


def on_sheet_start_example_1_seed_per_sheet_state(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table,
    write_table,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: seed a per-sheet dict in shared state (available to detectors/transforms)."""

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    sheets = state.setdefault("sheets", {})
    sheets.setdefault(sheet_name, {})


def on_sheet_start_example_2_stash_sheet_properties(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table,
    write_table,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: stash sheet properties in shared state for debugging/downstream logic."""

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    sheets = state.setdefault("sheets", {})
    sheets[sheet_name] = {
        "max_row": getattr(sheet, "max_row", None),
        "max_col": getattr(sheet, "max_column", None),
        "sheet_state": getattr(sheet, "sheet_state", None),  # "visible" / "hidden"
    }


def on_sheet_start_example_3_enrich_metadata(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table,
    write_table,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: enrich metadata (keep it small/serializable) for downstream logs."""

    if not isinstance(metadata, dict):
        return
    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    metadata["sheet_name_normalized"] = sheet_name.strip().lower()


def on_sheet_start_example_4_emit_structured_event(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table,
    write_table,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: emit a structured config event (safe under engine.config.*)."""

    if not logger:
        return

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    sheet_index = 0
    if isinstance(metadata, dict):
        try:
            sheet_index = int(metadata.get("sheet_index", 0) or 0)
        except (TypeError, ValueError):
            sheet_index = 0

    logger.event(
        "config.sheet.start",
        data={"sheet_name": sheet_name, "sheet_index": sheet_index},
    )


def on_sheet_start_example_5_fail_fast_blank_sheet_name(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table,
    write_table,
    input_file_name: str | None,
    logger,
) -> None:
    """Example: fail fast if a sheet looks wrong."""

    sheet_name = getattr(sheet, "title", getattr(sheet, "name", ""))
    if not sheet_name or sheet_name.strip() == "":
        raise ValueError("Sheet name is blank; check input workbook")

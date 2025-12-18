from __future__ import annotations


# Hook: on_workbook_start
#
# When this runs
# - Once per input file, after ADE has opened the input workbook.
# - Before any sheets/tables are processed (so `sheet` and `table` are `None` here).
# - The `workbook` passed to this hook is the *source* workbook (read-only); use
#   `on_workbook_before_save` for edits to the *output* workbook.
#
# What it's useful for
# - Initializing run-scoped `state` that other hooks can read/write.
# - Inspecting workbook properties (sheet names, counts, etc.) to drive behavior.
# - Failing fast when an input workbook doesn't match expectations (raise an error).
# - Emitting config-specific events (prefer the `engine.config.*` namespace).
#
# What you get
# - `metadata` usually includes: `input_file`, `output_file`, `input_file_name`.
# - `state` is a plain dict shared across the entire run (all sheets/tables).
# - `logger` is a run-scoped logger (safe to call with `if logger:`).
def register(registry):
    registry.register_hook(on_workbook_start, hook="on_workbook_start", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_workbook_start_example_1_fail_fast_missing_sheets, hook="on_workbook_start", priority=0)
    # registry.register_hook(on_workbook_start_example_2_set_workbook_flags, hook="on_workbook_start", priority=0)
    # registry.register_hook(on_workbook_start_example_3_emit_structured_event, hook="on_workbook_start", priority=0)


def on_workbook_start(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run metadata (filenames, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # Source workbook (openpyxl Workbook)
    sheet,  # Always None for this hook
    table,  # Always None for this hook
    write_table,  # Always None for this hook
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> None:
    """Workbook lifecycle hook (called once per run, before sheet processing)."""

    # Seed shared run state. Everything in `state` is available to later hooks.
    state.setdefault("notes", [])
    state.setdefault("stats", {"sheets_seen": 0, "tables_seen": 0})

    sheet_names = list(getattr(workbook, "sheetnames", []) or [])
    state.setdefault("sheet_names", sheet_names)

    if logger:
        logger.info(
            "Config hook: workbook start (input=%s, sheets=%d)",
            metadata.get("input_file") or input_file_name or "",
            len(sheet_names),
        )


def on_workbook_start_example_1_fail_fast_missing_sheets(
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
    """Example: fail fast if required worksheets are missing."""

    required = {"Orders", "Customers"}
    sheet_names = list(getattr(workbook, "sheetnames", []) or [])
    missing = sorted(required - set(sheet_names))
    if missing:
        raise ValueError(f"Missing required worksheet(s): {', '.join(missing)}")


def on_workbook_start_example_2_set_workbook_flags(
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
    """Example: store workbook-level flags for later hooks (like transforms/validators)."""

    state["vendor"] = "acme"
    state["treat_blank_as_null"] = True


def on_workbook_start_example_3_emit_structured_event(
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
    """Example: emit a config-scoped event (no strict schema required)."""

    if not logger:
        return

    sheet_names = list(getattr(workbook, "sheetnames", []) or [])
    cfg_logger = logger.with_namespace("engine.config")
    cfg_logger.event(
        "workbook.start",
        data={"input_file": metadata.get("input_file"), "sheet_names": sheet_names},
    )

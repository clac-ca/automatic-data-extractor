# Hooks Guide

Hooks let config packages run code at specific points in the engine lifecycle. Register hooks with `registry.register_hook(fn, hook="<hook_stage>", priority=...)`.

## Hook stages

1. `on_workbook_start` — before any sheets are processed.
2. `on_sheet_start` — per sheet, before table detection/mapping.
3. `on_table_mapped` — after mapping (mapping is rename-only), before transforms.
4. `on_table_transformed` — after transforms, before validation.
5. `on_table_validated` — after validation, before write (final shaping).
6. `on_table_written` — after the table is written to the output worksheet (formatting/summaries).
7. `on_workbook_before_save` — final hook, receives the output workbook just before `save()`.

## Table hook return semantics

For these stages, hooks may replace the DataFrame:

- `on_table_mapped`
- `on_table_transformed`
- `on_table_validated`

Rules:

- Hooks run in priority order.
- If a hook returns a `pl.DataFrame`, it becomes the input to the next hook in that stage.
- If it returns `None`, the table is unchanged.
- Any other return type raises `HookError`.

For all other hooks (including `on_table_written`), the hook must return `None`.

## Context and state

All hooks receive a `HookContext` expanded into keyword arguments by `call_extension`. Common fields:

- `metadata`: dict (filenames, sheet index, etc.)
- `settings`: engine settings
- `state`: mutable dict shared across the run
- `workbook`: workbook object (varies by stage)
- `sheet`: worksheet object (varies by stage)
- `table`: `pl.DataFrame | None` (for `on_table_written`, this is the DataFrame that was written after output policies)
- `region`: `TableRegion | None` (source region for `on_table_*`; output region for `on_table_written`)
- `table_index`: `int | None` (0-based index within the sheet)
- `input_file_name`: `str | None`
- `logger`: `RunLogger`

Mutating `state` is the preferred way to share data between hooks, detectors, transforms, and validators.

## Error handling and ordering

- Any exception in a hook is wrapped as `HookError` with the stage name; the run fails.
- Hooks are sorted by `priority` (desc), then module + qualname (deterministic).

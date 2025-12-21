# Hooks Guide

Hooks let config packages run code at specific points in the engine lifecycle. Register hooks with `registry.register_hook(fn, hook="<hook_stage>", priority=...)`.

## Hook stages

1. `on_workbook_start` — before any sheets are processed.
2. `on_sheet_start` — per sheet, before table detection/mapping.
3. `on_table_mapped` — after mapping (mapping is rename-only), before transforms.
4. `on_table_transformed` — after transforms, before validation.
5. `on_table_validated` — after validation, before write (final shaping).
6. `on_table_written` — after the table is written to the output worksheet (formatting/summaries).
7. `on_sheet_end` — per sheet, after all tables are written to the output worksheet.
8. `on_workbook_before_save` — final hook, receives the output workbook just before `save()`.

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

For all other hooks (including `on_table_written` and `on_sheet_end`), the hook must return `None`.

## Context and state

Hooks receive a stage-specific context expanded into keyword arguments by `call_extension`.
The engine only passes parameters that are populated for that stage:

- `on_workbook_start`: `source_workbook`, `input_file_name`, `settings`, `metadata`, `state`, `logger`
- `on_sheet_start`: `source_sheet`, `source_workbook`, `input_file_name`, `settings`, `metadata`, `state`, `logger`
- `on_sheet_end`: `output_sheet`, `output_workbook`, `tables`, `input_file_name`, `settings`, `metadata`, `state`, `logger`
- `on_table_mapped` / `on_table_transformed` / `on_table_validated`: `table`, `source_sheet`, `source_workbook`, `source_region`, `table_index`, `input_file_name`, `settings`, `metadata`, `state`, `logger`
- `on_table_written`: `write_table`, `output_sheet`, `output_workbook`, `output_region`, `table_index`, `table_result`, `input_file_name`, `settings`, `metadata`, `state`, `logger`
- `on_workbook_before_save`: `output_workbook`, `input_file_name`, `settings`, `metadata`, `state`, `logger`

Notes:

- `source_*` values are always from the input workbook; `output_*` values are always from the output workbook.
- `tables` is ordered in the same top-to-bottom order the tables were written.
- `source_region` / `output_region` use Excel-style bounds (`min_row/min_col/max_row/max_col` are 1-based + inclusive; `min_row` is the header row). Use `.a1` for an `"A1:D10"`-style range.

`state` remains available for cross-stage sharing, but `table_result` and `tables` cover most diagnostics without extra bookkeeping.

## Error handling and ordering

- Any exception in a hook is wrapped as `HookError` with the stage name; the run fails.
- Hooks are sorted by `priority` (desc), then module + qualname (deterministic).

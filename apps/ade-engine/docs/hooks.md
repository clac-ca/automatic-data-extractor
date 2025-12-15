# Hooks Guide

Hooks let config packages run code at specific points in the Engine lifecycle. Register hooks with `registry.register_hook(fn, hook_name=HookName.<name>, priority=...)`.

## Hook order and timing

1. `on_workbook_start` — before any sheets are processed. Inputs:
   - `workbook`: source workbook (read-only for XLSX; in-memory for CSV)
   - `sheet`: `None`
   - `table`: `None`
   - Use cases: per-run initialization, metadata capture, state seeding.

2. `on_sheet_start` — per sheet, before detection/mapping.
   - `sheet`: source worksheet
   - Use cases: sheet-level skips, state resets, exploratory logging.

3. `on_table_detected` — after row + column detection, before transforms.
   - `table`: `TableData` with `source_columns`, `mapped_columns`, `unmapped_columns`, `header_row_index`.
   - Use cases: inspect mapping, stash intermediate structure in `state`.

4. `on_table_mapped` — immediately after `on_table_detected`; last chance to patch mapping.
   - Mutating `table.mapped_columns` / `table.unmapped_columns` is allowed.
   - Use cases: reorder mapped columns, drop/merge mappings, apply custom tie-break rules.

5. `on_table_written` — after transforms/validators and after the table is rendered to the output worksheet.
   - `sheet`: output worksheet
   - `table.columns` contains the canonical column store; `table.issues_patch` contains vector-aligned issues; `table.issues` is the flattened issues list.
   - Use cases: write summaries, create additional sheets, append totals, reorder output columns.

6. `on_workbook_before_save` — final hook, receives the output workbook just before `save()`.
   - Use cases: add cover sheets, global formatting, run consistency checks.

## Context and state

All hooks receive a `HookContext` with:
- `metadata`: dict (includes `input_file` / `output_file` names)
- `state`: mutable dict shared across the entire run
- `input_file_name`: source filename (str | None)
- `logger`: `RunLogger` scoped to the run

Mutating `state` is the preferred way to share data between hooks, detectors, transforms, and validators.

## Error handling

Any exception in a hook is wrapped as `HookError` with the stage name; the run fails. Log diagnostics via the provided `logger` instead of printing.

## Priorities

Hooks are sorted by `priority` (desc), then module + qualname. Use higher numbers to run earlier within the same stage.

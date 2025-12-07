# Hooks (Workbook → Sheet → Table)

Hooks are optional `run(**kwargs)` entrypoints that let you observe or decorate the pipeline without replacing it. Configure them under `"hooks"` in `manifest.toml`.

## Lifecycle

1. `on_workbook_start(run_ctx)` — called once after workbooks are created.
2. `on_sheet_start(sheet_ctx, run_ctx)` — once per source sheet before detection.
3. `on_table_detected(table_ctx, run_ctx)` — after extraction, before mapping.
4. `on_table_mapped(table_ctx, run_ctx)` — may return `ColumnMappingPatch` to override mapping.
5. `on_table_written(table_ctx, run_ctx)` — after a table is rendered; safe place for styles/comments.
6. `on_workbook_before_save(run_ctx)` — final adjustments before saving.

## Contexts

* `run_ctx`: `RunContext` with source/output workbooks and manifest plus a shared `state` dict.
* `sheet_ctx`: `WorksheetContext` with `source_worksheet` and `output_worksheet`.
* `table_ctx`: `TableContext` exposing `extracted`, `mapped`, `normalized`, and `view`/`placement` for styling.

Only `on_table_mapped` should return a value (`ColumnMappingPatch | None`); other hooks return `None`.

**Safety:** Hooks should avoid inserting/deleting rows or columns outside the renderer’s `TablePlacement`; apply styles/comments within the provided `TableView` range.

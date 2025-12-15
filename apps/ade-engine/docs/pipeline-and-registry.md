# Pipeline + Registry

This document describes how the pipeline consumes the Registry that config packages populate.

## Registry lifecycle

1. **Creation** — `Engine._load_registry` instantiates a fresh `Registry`.
2. **Population** — The config package’s `register(registry)` function should call `registry.register_*` for all detectors, transforms, validators, hooks, and fields. No decorators or registry context are required.
3. **Finalization** — `registry.finalize()`:
   - Sorts detectors/transforms/validators/hooks by `priority` (desc), then module + qualname for deterministic ordering.
   - Groups transforms/validators by `field` for fast lookup during the run.

## Sheet pipeline steps

1. **Materialize rows**  
   `_materialize_rows` streams worksheet rows into a trimmed list while enforcing guards:
   - Trailing empty cells beyond `max_empty_cols_run` are dropped per row.
   - Scanning stops after `max_empty_rows_run` consecutive empty rows (if configured).

2. **Detect table regions** (`detect_table_regions`)  
   - For each row, run `registry.row_detectors` with `RowDetectorContext`.
   - Each detector returns score patches keyed by `RowKind` (`header`, `data`, `unknown`). Scores are summed per row.
   - The pipeline segments a sheet into multiple `TableRegion`s:
     - A table starts at a detected `header`.
     - Data ends at the next header (exclusive) or the sheet end.
     - If a `data` row appears before any header, the row above is treated as an inferred header unless it is empty (then the current row becomes the header).
     - Fallback: if no header can be inferred/detected, use the best header score; if there is no positive signal, use the first non-empty row.

3. **Per-table processing**  
   For each detected `TableRegion`, the pipeline repeats steps 4–10 below and appends the rendered output to the same output worksheet (with a blank row between tables).

4. **Build source columns** (`build_source_columns`)  
   The header row and data rows are sliced into `SourceColumn` objects (index, header cell, column values).

5. **Detect + map columns** (`detect_and_map_columns`)  
   - Run `registry.column_detectors` for each source column. Detectors return score patches keyed by **field name**.
   - Columns with no positive total score are left unmapped.
   - Duplicate resolution per field:
     - `mapping_tie_resolution="leftmost"` (default): keep the highest score; if tied, keep the leftmost column and mark others unmapped.
     - `"leave_unmapped"`: if more than one column maps to a field, mark them all unmapped.
   - Output: ordered `mapped_columns` (by source index) and `unmapped_columns`.

6. **Hooks: mapping**  
   - `on_table_detected` receives the `TableData` right after mapping.
   - `on_table_mapped` can reorder or patch mappings before transforms run.

7. **Transforms** (`apply_transforms`)  
   - The canonical table is treated as a column store (`dict[field, vector]`), with `N` data rows.
   - Transforms run deterministically in two phases:
     - Phase 1: mapped fields in source column order.
     - Phase 2: derived-only fields currently present that have transforms registered (registry field order).
   - Each transform receives `field_name`, `column` (vector), and a read-only `TableView` for cross-field inspection.
   - A transform may return:
     - `None` (no change)
     - a replacement vector for the owner field
     - a values patch (`dict[field, vector]`) to emit derived fields
     - a table patch envelope including optional issues/meta
   - Unknown fields or wrong-length vectors raise `PipelineError`.
   - Derived field writes use `derived_write_mode` (default `fill_missing`) to avoid stomping existing values.

8. **Validators** (`apply_validators`)  
   - Validators run after all transforms complete (including phase 2 derived transforms), with the same phasing + deterministic ordering rules.
   - Each validator receives `field_name`, `column` (vector), and `TableView`.
   - Validators return either sparse issues (`[{"row_index": ..., "message": ...}, ...]`) or issue vectors (`dict[field, issue_vec]`), optionally wrapped in a table patch envelope.
   - Issues are normalized into a vector-aligned `issues_patch`, then flattened into `table.issues`.

9. **Render** (`render_table`)  
   - Write canonical headers in order:
     1. mapped fields (source order)
     2. derived canonical fields present in the table (registry field order) when `render_derived_fields=True`
     3. appended unmapped source columns when `append_unmapped_columns=True` (prefixed by `unmapped_prefix`)
   - Emit `N` data rows (with a guard to include appended unmapped columns even if no canonical fields are mapped).

10. **Hooks: after write**  
   - `on_table_written` runs with the output worksheet and `TableData` (including `rows` and `issues`).

## Logging touchpoints

The pipeline emits structured events when `RunLogger` is in use:

- `detector.*` and `row_classification` / `column_classification` for detector scores
- `transform.result`, `transform.derived_merge`
- `validation.result`, `validation.summary`
- `table.written`

Engine-level hooks log start/end around hook execution. Use `--log-format ndjson --debug` for full telemetry.

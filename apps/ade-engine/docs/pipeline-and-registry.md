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

2. **Detect table bounds** (`detect_table_bounds`)  
   - For each row, run `registry.row_detectors` with `RowDetectorContext`.
   - Each detector returns score patches keyed by `RowKind` (`header`, `data`, `unknown`). Scores are summed per row.
   - Header selection rules:
     - First row classified as `header` wins.
     - If a `data` row appears before any header, the row above is treated as the header.
     - Data ends at the next header (exclusive) or the sheet end.
     - Fallback: best header score; if no signal, first non-empty row.

3. **Build source columns** (`build_source_columns`)  
   The header row and data rows are sliced into `SourceColumn` objects (index, header cell, column values).

4. **Detect + map columns** (`detect_and_map_columns`)  
   - Run `registry.column_detectors` for each source column. Detectors return score patches keyed by **field name**.
   - Columns with no positive total score are left unmapped.
   - Duplicate resolution per field:
     - `mapping_tie_resolution="leftmost"` (default): keep the highest score; if tied, keep the leftmost column and mark others unmapped.
     - `"leave_unmapped"`: if more than one column maps to a field, mark them all unmapped.
   - Output: ordered `mapped_columns` (by source index) and `unmapped_columns`.

5. **Hooks: mapping**  
   - `on_table_detected` receives the `TableData` right after mapping.
   - `on_table_mapped` can reorder or patch mappings before transforms run.

6. **Transforms** (`apply_transforms`)  
   - For each mapped field, run its transforms in priority order. Each transform must return a list of `ColumnTransformResult` (one per row).
   - Missing/duplicate row indices or shape mismatches raise `PipelineError`.
   - Transform outputs are merged into row dicts; a transform may add extra keys to introduce derived columns.

7. **Validators** (`apply_validators`)  
   - For each mapped field, run validators (priority order) with the transformed values. Each returns a list of `ColumnValidatorResult`.
   - Issues are collected into `table.issues` but do **not** fail the run unless the validator itself raises.

8. **Render** (`render_table`)  
   - Write headers for mapped columns (field names). If `append_unmapped_columns=True`, append unmapped headers prefixed by `unmapped_prefix` (default `raw_`; fallback header `col_<n>`).
   - Emit as many data rows as the longest of mapped or appended unmapped columns.

9. **Hooks: after write**  
   - `on_table_written` runs with the output worksheet and `TableData` (including `rows` and `issues`).

## Logging touchpoints

The pipeline emits structured events when `RunLogger` is in use:

- `detector.*` and `row_classification` / `column_classification` for detector scores
- `transform.result`, `transform.overwrite`
- `validation.result`
- `table.written`

Engine-level hooks log start/end around hook execution. Use `--log-format ndjson --debug` for full telemetry.

## Current limitation

Only **one table per worksheet** is processed. Detection stops after the first header→data region is rendered. The planned multi-table refactor will loop detection/rendering per sheet; until then, place only one table per sheet when authoring config packages. See `src/ade_engine/pipeline/README.md` for details.

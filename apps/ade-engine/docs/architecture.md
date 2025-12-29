# ADE Engine Architecture

ADE Engine is a plugin-driven spreadsheet normalizer. The runtime is split into a small number of focused components that cooperate during a single run:

- **Engine** (`ade_engine.application.engine.Engine`) — orchestrates a run: loads settings, prepares output/log paths, loads the config package into a Registry, iterates sheets, fires hooks, and saves the workbook.
- **Pipeline** (`ade_engine.application.pipeline.pipeline.Pipeline`) — sheet-level processing: detect the table region, map columns, transform values, validate issues, render the normalized table, and emit lifecycle hooks.
- **Registry** (`ade_engine.extensions.registry.Registry`) — in-memory container populated by config-package calls to `registry.register_*`. Holds fields plus registered detectors, transforms, validators, and hooks ordered by priority.
- **IO helpers** (`ade_engine.infrastructure.io`) — normalize paths, open source workbooks (CSV/XLSX), create empty output workbooks, and resolve sheet selection.
- **Logging** (`ade_engine.infrastructure.observability.logger.RunLogger`) — structured log/event stream with text or NDJSON output for every run.
- **Settings** (`ade_engine.infrastructure.settings.Settings`) — runtime toggles for mapping, output ordering, logging, scan guards, and supported extensions.

## End-to-end flow

1. **Prepare run**  
   `Engine.run` takes a `RunRequest` (CLI constructs this) and resolves paths via `plan_run` (`ade_engine.infrastructure.io.run_plan`). Output/log directories are created if they do not exist. If a log file path is not provided, the engine derives a per-input log filename automatically.

2. **Start logging**  
   A `RunLogger` is created with the configured format/level (`text` or `ndjson`). All engine events flow through this logger, including structured detector/transform/validator telemetry.

3. **Load config package into the Registry**  
   - The config package path is resolved to an importable package name (supports bare package dir, `src/<package>`, or a root containing `ade_config`).
   - The engine auto-discovers plugin modules under `<package>/columns/`, `<package>/row_detectors/`, and `<package>/hooks/`. Any module in those folders that defines `register(registry)` is imported and invoked (deterministic order; no central list).
   - Each plugin module’s `register(registry)` should call `registry.register_*` for every detector/transform/validator/hook/field it provides. The CLI (or your app) loads runtime settings from `settings.toml` / `.env` / env vars via `Settings.load(...)`.
   - Loading is done with a scoped `sys.path` insertion and a module purge to avoid cross-run contamination when multiple packages share the same name (common with `ade_config`).
   - After registration, `registry.finalize()` sorts callables by priority and groups transforms/validators by field.

4. **Process workbook**  
   The source workbook is opened (CSV files are converted to an in-memory workbook). Visible sheets are chosen either from the source order or filtered by `--input-sheet`. A shared `state` dict and `metadata` (input/output filenames) travel through hooks and pipeline stages.

5. **Sheet pipeline**  
   For each sheet, the engine fires `on_sheet_start` (input workbook), then `Pipeline.process_sheet` performs:
   - `detect_table_regions`: run row detectors to classify each row and segment the sheet into one or more table regions.
   - For each table region:
     - `detect_and_map_columns`: map source columns to registered fields and resolve duplicates per `mapping_tie_resolution`.
     - Materialize one `pl.DataFrame` immediately after extraction (minimal header normalization).
     - Apply mapping as a rename-only step on the same DataFrame.
     - Hook: `on_table_mapped` (may replace the DataFrame).
     - `apply_transforms`: run v3 transforms (Polars expressions) to add/replace columns.
     - Hook: `on_table_transformed` (may replace the DataFrame).
     - `apply_validators`: run v3 validators to write inline issue-message columns (`__ade_issue__*`).
     - Hook: `on_table_validated` (may replace the DataFrame; safe to filter/sort/reorder).
     - `render_table`: derive `write_table` using output settings and write it directly to the output sheet.
     - Hook: `on_table_written` (formatting/summaries; receives `write_table` plus `table_result` facts).
   After all tables are written, the engine fires `on_sheet_end` with the output workbook/worksheet and the list of `TableResult` objects.

6. **Finalize workbook**  
   Hook `on_workbook_before_save` fires with the output workbook, then the workbook is saved to `<output_dir>/<input_stem>_normalized.xlsx` (or a caller-specified path).

7. **Result**  
   `RunResult` reports status, error (if any), output path, logs dir, and processed filename.

## Execution model & limitations

- Processing is **per-run, per-sheet**, and a sheet may contain **multiple tables** (segmented by header detection).
- Input formats: `.xlsx`, `.xlsm`, `.csv` (configurable via `Settings.supported_file_extensions`).
- Sheets are read with `openpyxl` (`read_only=True` for XLSX). `_materialize_rows` guards against runaway empty rows/columns using `max_empty_rows_run` and `max_empty_cols_run`.
- A shared `state` dict lets hooks, detectors, transforms, and validators pass data across stages and sheets; mutating it is safe within a single run.
- Failures in hooks or pipeline stages surface as `RunError` with stage-specific codes (`config_error`, `input_error`, `hook_error`, `pipeline_error`, `unknown_error`).

## Key extension points

- **Detectors** vote on header/data rows and column-to-field mapping.
- **Transforms** return Polars expressions and can emit additional columns by returning a `dict[str, Expr]`.
- **Validators** return issue-message expressions; the engine writes issues inline as reserved columns (`__ade_issue__*`).
- **Hooks** wrap workbook and table lifecycle moments for custom side effects (telemetry, reordering, extra worksheets, etc.).

Use `apps/ade-engine/docs/callable-contracts.md` for the exact signatures and return contracts of each extension type.

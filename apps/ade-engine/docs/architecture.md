# ADE Engine Architecture

ADE Engine is a plugin-driven spreadsheet normalizer. The runtime is split into a small number of focused components that cooperate during a single run:

- **Engine** (`ade_engine.engine.Engine`) — orchestrates a run: loads settings, prepares output/log paths, loads the config package into a Registry, iterates sheets, fires hooks, and saves the workbook.
- **Pipeline** (`ade_engine.pipeline.Pipeline`) — sheet-level processing: detect the table region, map columns, transform values, validate issues, render the normalized table, and emit lifecycle hooks.
- **Registry** (`ade_engine.registry.Registry`) — in-memory container populated by config-package calls to `registry.register_*`. Holds fields plus registered detectors, transforms, validators, and hooks ordered by priority.
- **IO helpers** (`ade_engine.io`) — normalize paths, open source workbooks (CSV/XLSX), create empty output workbooks, and resolve sheet selection.
- **Logging** (`ade_engine.logging.RunLogger`) — structured log/event stream with text or NDJSON output for every run.
- **Settings** (`ade_engine.settings.Settings`) — runtime toggles for mapping, output ordering, logging, scan guards, and supported extensions.

## End-to-end flow

1. **Prepare run**  
   `Engine.run` takes a `RunRequest` (CLI constructs this) and resolves paths via `plan_run` (`ade_engine.io.paths`). Output/log directories are created if they do not exist. If a log file path is not provided, the engine derives a per-input log filename automatically.

2. **Start logging**  
   A `RunLogger` is created with the configured format/level (`text` or `ndjson`). All engine events flow through this logger, including structured detector/transform/validator telemetry.

3. **Load config package into the Registry**  
   - The config package path is resolved to an importable package name (supports bare package dir, `src/<package>`, or a root containing `ade_config`).
   - The package **must** expose `register(registry)`, and that function should call `registry.register_*` for every detector/transform/validator/hook/field it provides. The CLI (or your app) loads runtime settings from `settings.toml` / `.env` / env vars via `Settings.load(...)`.
   - Loading is done with a scoped `sys.path` insertion and a module purge to avoid cross-run contamination when multiple packages share the same name (common with `ade_config`).
   - After registration, `registry.finalize()` sorts callables by priority and groups transforms/validators by field.

4. **Process workbook**  
   The source workbook is opened (CSV files are converted to an in-memory workbook). Visible sheets are chosen either from the source order or filtered by `--input-sheet`. A shared `state` dict and `metadata` (input/output filenames) travel through hooks and pipeline stages.

5. **Sheet pipeline**  
   For each sheet, `Pipeline.process_sheet` performs:
   - `detect_table_regions`: run row detectors to classify each row and segment the sheet into one or more table regions.
   - For each table region:
     - `detect_and_map_columns`: map source columns to registered fields, resolve duplicates per `mapping_tie_resolution`, and split mapped vs. unmapped columns.
     - Hooks: `on_table_detected` then `on_table_mapped`.
     - `apply_transforms`: run column transforms for each mapped field, enforcing the strict row-output contract.
     - `apply_validators`: run column validators to collect issue payloads.
     - `render_table`: write headers + rows to the output sheet, optionally appending unmapped columns.
     - Hook: `on_table_written`.

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
- **Transforms** normalize per-field values and can emit additional columns by returning extra keys in the row payload.
- **Validators** emit structured issues; the engine does not stop on validation failures—it records them in `TableData.issues`.
- **Hooks** wrap workbook and table lifecycle moments for custom side effects (telemetry, reordering, extra worksheets, etc.).

Use `apps/ade-engine/docs/callable-contracts.md` for the exact signatures and return contracts of each extension type.

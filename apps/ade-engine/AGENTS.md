## Mental model: what the ADE engine fundamentally is

At its core, this repo is a **plugin-driven spreadsheet normalizer**:

* **Input**: an XLSX/CSV (workbook), plus a **config package** (Python code) that defines:

  * how to find the **header row** (row detectors),
  * how to map **source columns → canonical fields** (column detectors),
  * how to normalize values (transforms),
  * how to validate values (validators),
  * and optional lifecycle hooks (workbook/sheet/table).
* **Output**: a new XLSX where:

  * mapped columns are written in canonical order (field names),
  * optionally “raw_…” passthrough columns are appended,
  * validations are collected as issue objects (currently not written into the workbook—just kept in memory/logs).

There are three main moving parts:

1. **Engine** (orchestration + IO + config loading)
2. **Pipeline** (sheet/table processing logic)
3. **Registry** (plugin container populated by decorators in config packages)

---

## End-to-end control flow (what happens on a run)

### 1) Request normalization + output/log planning

`Engine.run()` creates a `RunRequest` (or uses one passed in) and normalizes it via `prepare_run_request()`:

* resolves `config_package`, `input_file`, `output_dir`
* derives `output_file` = `<output_dir>/<input_stem>_normalized.xlsx` unless specified
* sets `logs_dir/logs_file` defaults

### 2) Run-scoped structured logging

A run-scoped `RunLogger` is created via `create_run_logger_context(...)`.

It produces structured events and has a schema policy:

* `engine.*` strict (must be registered, payload validated)
* `engine.config.*` open (freeform)

### 3) Load config package into a fresh Registry

`Engine._load_registry()`:

* creates a new `Registry()`
* resolves the config path into:

  * an importable package name
  * a sys.path root (added to `sys.path`)
* enters `registry_context(registry)` (contextvar)
* imports the config package and *all submodules* (`import_all(...)`), which triggers decorator registration into the active registry
* `registry.finalize()` sorts everything deterministically

### 4) Open source workbook + create output workbook

* CSV is loaded into an in-memory openpyxl workbook
* XLSX is loaded read-only (`openpyxl.load_workbook(read_only=True, data_only=True)`)

### 5) Workbook/sheet lifecycle

For each selected sheet:

* engine runs `ON_WORKBOOK_START`, `ON_SHEET_START` hooks
* pipeline runs table-level processing

### 6) Pipeline.process_sheet()

This is the normalization pipeline for one sheet:

1. **Materialize rows**
   In `src`, `_materialize_rows()` trims long trailing empties and stops after large empty runs (good guardrails).

2. **Detect table bounds**
   `detect_table_bounds()` runs row detectors on each row to classify row kinds. It returns:

   * `header_idx`
   * `data_start_idx`
   * `data_end_idx` (stops at next detected header)

3. **Build source columns + detect & map canonical fields**
   `build_source_columns(header_row, data_rows)` creates `SourceColumn(index, header, values)` objects.

   `detect_and_map_columns(...)` runs **all column detectors** for each column, accumulates scores, picks best field, then resolves collisions (two columns mapping to same field) according to settings.

4. **Hooks**

   * `ON_TABLE_DETECTED`
   * `ON_TABLE_MAPPED`
     Hooks currently mutate `TableData` directly if they want to affect mapping/behavior.

5. **Transforms**
   `apply_transforms()` runs column transforms for each mapped field (in priority order), producing `table.rows` as a list of dicts (row-wise records).

6. **Validators**
   `apply_validators()` runs validators per mapped field and collects failures into `table.issues` (list of dicts).

7. **Render**
   `render_table()` writes:

   * header row: canonical fields + `raw_...` passthrough
   * data rows: mapped data from `table.rows` + unmapped passthrough values

8. **Hook**

   * `ON_TABLE_WRITTEN`

### 7) Save output + return RunResult

Engine runs `ON_WORKBOOK_BEFORE_SAVE`, saves output workbook, returns `RunResult`.
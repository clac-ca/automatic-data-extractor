# Testing & Quality

This document describes how we test **`ade_engine`** and what “good” test
coverage means for this project.

It is written for engine maintainers and advanced config authors who need to
understand how the runtime behaves and how to keep changes safe and
predictable over time.

## Terminology

| Concept        | Term in code      | Notes                                                     |
| -------------- | ----------------- | --------------------------------------------------------- |
| Run            | `run`             | One call to `Engine.run()` or one CLI invocation          |
| Config package | `config_package`  | Installed `ade_config` package for this run               |
| Config version | `manifest.version`| Version declared by the config package manifest           |
| Build          | build             | Virtual environment built for a specific config version   |
| User data file | `source_file`     | Original spreadsheet on disk                              |
| User sheet     | `source_sheet`    | Worksheet/tab in the spreadsheet                          |
| Canonical col  | `field`           | Defined in manifest; never call this a “column”           |
| Physical col   | column            | B / C / index 0,1,2… in a sheet                           |
| Output workbook| normalized workbook| Written to `output_dir`; includes mapped + normalized data|

Tests and fixtures should use the same vocabulary as runtime and docs.

---

## 1. Goals and principles

Our testing strategy is built around a few simple ideas:

- **Deterministic behavior**  
  Given the same `ade_config`, manifest, and source files, the engine should
  produce the **same** normalized workbook and `events.ndjson`.

- **Separation of concerns**  
  Each layer should be testable in isolation:
  - IO and table detection,
  - column mapping,
  - normalization and validation,
- telemetry (events.ndjson),
  - high‑level `Engine.run`.

- **Stable contracts**  
  The shapes and semantics of:
  - `RunRequest` / `RunResult`,
  - `events.ndjson`,
  - script entrypoints in `ade_config`
  
  are treated as **contracts**. Tests should make it obvious when a change
  breaks those contracts.

- **Fast feedback first, deep coverage second**  
  Unit tests should run very quickly and catch most issues. Integration tests
  cover cross‑cutting behavior, including venv and config usage.

The rest of this document explains how tests are organized and what we expect
from each layer.

---

## 2. Test layout

All tests live under the top‑level `tests/` directory.

A typical structure:

```text
apps/ade-engine/
  ade_engine/
    ...
  tests/
    pipeline/
      test_io.py
      test_extract.py
      test_mapping.py
    test_normalize.py
    test_write.py
  test_engine_runtime.py
  test_config_loader.py  # legacy name in repo: test_config_runtime_loader.py
  test_telemetry.py
  test_cli.py
  fixtures/
    __init__.py
      config_factories.py
      sample_inputs.py
````

We assume pytest for examples, but nothing here depends on a specific test
framework.

### 2.1 Unit tests

Unit tests live close to the corresponding module:

* `tests/pipeline/test_io.py` → `ade_engine/io.py`
* `tests/pipeline/test_extract.py` → `pipeline/extract.py`
* `tests/pipeline/test_mapping.py` → `pipeline/mapping.py`
* `tests/pipeline/test_normalize.py` → `pipeline/normalize.py`
* `tests/pipeline/test_write.py` → `pipeline/write.py`
* `tests/test_engine_runtime.py` → `engine.py`, `types.py`
* `tests/test_config_loader.py` (legacy: `test_config_runtime_loader.py`) → `config/loader.py`, `schemas/manifest.py`
* `tests/test_telemetry.py` → `telemetry.py`
* `tests/test_cli.py` → `cli.py`, `__main__.py`

Goal: cover small units and pure functions with precise, focused assertions.

### 2.2 Integration tests

Integration tests exercise the engine end‑to‑end with a synthetic `ade_config`
and real files:

* Create a temporary `ade_config` package (see fixtures below).
* Write a `manifest.json`.
* Write simple detector / transform / validator scripts.
* Invoke the engine:

  * via Python API (`ade_engine.run(...)`), and/or
  * via CLI (`python -m ade_engine ...`).
* Assert on:

  * `RunResult` status and paths,
  * workbook contents,
  * `events.ndjson` (telemetry timeline).

These tests live in the top‑level `tests/` folder (e.g., in
`test_engine_runtime.py` and `test_cli.py`) and act as contract tests for the
public API.

---

## 3. Fixtures & helpers

To keep tests readable, we centralize common setup in `tests/fixtures/`.

### 3.1 Temporary `ade_config` packages

`fixtures/config_factories.py` should provide helpers such as:

```python
def make_minimal_config(tmp_path) -> Path:
    """
    Create a minimal ade_config package under tmp_path and return its path.
    Includes:
      - manifest.json
      - row_detectors/header.py
      - column_detectors/member_id.py
      - hooks/on_run_start.py (optional)
    """
```

This factory should:

* Write a well‑formed `manifest.json` using the Pydantic `ManifestV1` model.
* Write config scripts with minimal, deterministic behavior.
* Ensure the temp directory is importable as `ade_config` (e.g., via `sys.path`
  manipulation).

This makes it easy for multiple tests to spin up isolated configurations with
different behaviors.

### 3.2 Sample inputs

`fixtures/sample_inputs.py` should expose helpers like:

* `sample_csv(tmp_path)` → path to a simple CSV file.
* `sample_xlsx_single_sheet(tmp_path)` → XLSX with one sheet and a small table.
* `sample_xlsx_multi_sheet(tmp_path)` → XLSX with multiple sheets and edge
  cases (empty rows, odd headers, etc.).

Tests should use these helpers instead of hand‑crafting spreadsheets in each
test file.

---

## 4. Unit testing by subsystem

This section lists what each subsystem should cover.

### 4.1 Engine runtime (`engine.py`, `types.py`)

Key tests:

* `RunRequest` validation:

  * Error if both `input_files` and `input_dir` are provided.
  * Error if neither is provided.
* `RunPaths` resolution:

  * Correct derivation of `input_dir`, `output_dir`, and `logs_dir` from
    `RunRequest`.
  * Directories are created if missing.
* `Engine.run` happy path:

  * With a mocked `ConfigRuntime` / pipeline, returns `RunResult` with
    expected paths and status.
* `Engine.run` failure path:

  * Inject an exception in the pipeline and ensure:

    * `RunResult.status == "failed"`,
    * `error` is set,
    * telemetry still records a `run.completed` with `status:"failed"` and error context.

Tests here should not depend on real `ade_config` packages; use mocks or
minimal in‑memory stubs.

### 4.2 Config runtime (`config/`, legacy `config_runtime/`, `schemas/manifest.py`)

Key tests:

* Manifest loading:

  * Loads from `manifest_path` override.
  * Loads from `ade_config/manifest.json` by default.
* Validation via `ManifestV1`:

  * Required fields enforced.
  * Optional fields default correctly.
* `ManifestContext` helpers:

  * `column_order`, `column_fields`, and `writer` behave as
    expected for typical manifests.
* Script discovery:

  * `ColumnModule` import and function discovery from `module` paths.
  * Hook module import and `run`/`main` determination.
* Failure modes:

  * Missing script modules or wrong signatures fail fast with clear errors.

### 4.3 IO and extraction (`io.py`, `pipeline/extract.py`)

Key tests:

* `list_input_files`:

  * Discovers only supported extensions.
  * Returns a predictable sort order.
* CSV reading:

  * Proper handling of UTF‑8 with/without BOM.
  * Stable row iteration for simple CSVs.
* XLSX reading:

  * Reads expected values from simple workbooks.
  * Honors `input_sheets` filters and raises appropriate errors for missing
    sheets.
* Table detection:

  * Produces `ExtractedTable` with correct header/data ranges given basic
    row detectors.
  * Handles empty sheets or sheets with no detectable table gracefully.

### 4.4 Column mapping (`pipeline/mapping.py`)

Key tests:

* Per‑column scoring:

  * Given controlled detector outputs, verify how scores are aggregated into
    `MappedColumn`.
* Threshold behavior:

  * Columns below the engine’s mapping threshold are not mapped (manifest v1 has no per-config override).
* Tie‑breaking:

  * Ties resolved by `manifest.columns.order`.
* Extra columns:

  * Unmapped columns become `UnmappedColumn`s when writer config says so.
  * `output_header` is generated deterministically.

### 4.5 Normalization and validation (`pipeline/normalize.py`)

Key tests:

* Canonical row construction:

  * Values are pulled correctly from `MappedTable.raw.data_rows` per mapping.
* Transform execution:

  * Transformers can mutate `row` and/or return update dicts.
  * Order of operations is deterministic.
* Validator execution:

  * Validation issues produced from simple validators.
  * `row_index` and `field` are populated correctly in `ValidationIssue`.

### 4.6 Writing output (`pipeline/write.py`)

Key tests:

* Single combined sheet:

  * Headers appear in `manifest.columns.order` followed by unmapped columns (if `append_unmapped_columns` is enabled).
  * Data rows written in stable, documented order.
* Per‑table sheet mode (if supported by writer config):

  * Per‑table sheet naming and collision handling.
* Hook integration:

  * `on_before_save` hooks can modify the workbook before save.
* Output paths:

  * Workbook saved to expected location under `output_dir`.

### 4.7 Telemetry (`telemetry.py`)

Key tests:

* Telemetry events:

  * `FileEventSink` writes well‑formed NDJSON.
  * Run logger and `EventEmitter` respect `min_*_level` thresholds on the configured sinks.
  * `run.started`, `run.table.summary`, `run.completed` payloads validate against schema.

---

## 5. Integration & end‑to‑end tests

Integration tests verify the engine’s behavior with a real `ade_config` and
filesystem, simulating how the ADE backend actually uses it.

### 5.1 End‑to‑end pipeline via Python API

Typical flow in `test_engine_runtime.py`:

1. Use `make_minimal_config(tmp_path)` to create a config package.

2. Add `tmp_path` to `sys.path` so `import ade_config` resolves.

3. Use `sample_xlsx_single_sheet(tmp_path)` to create an input.

4. Call:

   ```python
   from ade_engine import run

   result = run(
       config_package="ade_config",
       input_files=[input_path],
       output_dir=tmp_path / "output",
       logs_dir=tmp_path / "logs",
       metadata={"test_case": "basic_e2e"},
   )
   ```

5. Assert:

   * `result.status == "succeeded"`.
   * Workbook exists at each `output_paths` entry and is a valid XLSX.
   * `events.ndjson` exists and contains at least `run.started` and
     `run.completed` events.

### 5.2 CLI integration

In `test_cli.py`:

1. Create a temp `ade_config` and sample input as above.

2. Invoke the CLI with `subprocess.run`:

   ```python
   proc = subprocess.run(
       [
           sys.executable, "-m", "ade_engine",
           "--input", str(input_path),
           "--output-dir", str(output_dir),
           "--logs-dir", str(logs_dir),
       ],
       capture_output=True,
       text=True,
   )
   ```

3. Assert:

   * `proc.returncode == 0`.
   * `proc.stdout` parses as JSON with expected keys.
   * Paths listed in JSON summary exist on disk and match expectations.

These tests ensure the CLI and Python API behave consistently and honor the
same invariants.

---

## 6. Regression & contract tests

### 6.1 Mapping stability

Mapping behavior is central to the product; we want to avoid silent changes.

Recommended approach:

* For selected configurations and inputs:

  * Take a **snapshot** of `run.table.summary` payloads (mapped/unmapped columns, scores).
* Add a test that:

  * Runs the engine with the same inputs/config.
  * Compares the new telemetry snapshot to the stored one.
  * Fails if fields or scores differ unexpectedly.

When mapping behavior must change intentionally:

* Update the stored snapshot as part of the change.
* Mention the behavior change in the PR description / changelog.

### 6.2 Telemetry schema contracts

We treat `events.ndjson` as the primary external contract.

Tests should:

* Validate telemetry JSON against Pydantic models (and optional JSON Schemas).
* Assert key invariants, for example:

  * Every telemetry event envelope has `type`, `created_at`, and payload.
  * `run.table.summary` includes mapping + validation fields.
  * `run.completed` carries status, outputs, and optional error context.

If a breaking change to telemetry shapes is necessary, tests should make the
breakage explicit and force a deliberate version bump.

---

## 7. Performance & resource checks

The engine is designed to stream rows and avoid large in‑memory structures.

### 7.1 Large input smoke tests

We include a small number of “big input” tests that:

* Generate a large CSV or XLSX (e.g., 50k–100k rows) in a temp directory.
* Use a minimal config with simple detectors/transforms/validators.
* Run the engine and assert:

  * It completes in a reasonable time.
  * It does not raise memory‑related errors.

We do **not** try to do precise performance benchmarking in unit tests, only
to catch obvious regressions (e.g., accidentally loading entire files into
memory).

### 7.2 Guidance for config authors

Config‑level tests (in client repos) should:

* Avoid network calls and heavy I/O in detectors/transforms/validators.
* Prefer sampling (via `column_values_sample`) to scanning full columns.
* Use their own fixtures and tests for business logic, separate from engine
  tests.

---

## 8. Debugging & triage workflows

When tests fail, a few patterns help quickly identify where the problem lives.

### 8.1 Mapping and validation issues

* Inspect `events.ndjson` (or streamed events) for `run.table.summary` payloads:

  * Check `mapped_columns` / `unmapped_columns` for unexpected field/header matches.
  * Check validation aggregates for surprising issue counts.
* Add temporary assertions or `logger.debug` / `event_emitter.custom` calls in the failing area,
  then re‑run the specific test.

### 8.2 Script errors

Typical sources:

* Exceptions inside config detectors, transforms, validators, or hooks.
* Misconfigured manifest hook/column module strings.

Debugging steps:

1. Reproduce with a focused test using the failing config fixture.
2. Check error details in:

   * `RunResult.error`,
   * `events.ndjson` (`run.error` / `run.completed` with failure payload).
3. Add a minimal repro to `tests/test_config_loader.py` (legacy: `test_config_runtime_loader.py`) or
   `tests/test_engine_runtime.py` if the error indicates a gap in engine
   validation.

---

## 9. Change management checklist

Before merging a non‑trivial change to `ade_engine`, check:

1. **Tests updated**

   * Unit tests for affected modules.
   * Integration tests if behavior changed cross‑cutting concerns.

2. **Contracts respected**

* `RunRequest` and `RunResult` semantics preserved, or versioned if
  breaking.
* `events.ndjson` format preserved, or versioned with explicit tests.
* `events.ndjson` format preserved, or versioned with explicit tests.

3. **Performance considered**

   * Large‑input tests still pass.
   * No obvious new O(n²) patterns or unbounded structures.

4. **Docs updated**

   * README and relevant docs under `apps/ade-engine/docs/` reflect the new
     behavior.

If tests are failing for reasons that look like “expected breakage”, expand
the tests to encode the new behavior, then update snapshots and docs in the
same change.

---

With this testing layer in place, you should be able to evolve the engine
confidently: small unit changes are caught early, and contract tests guard the
interfaces that ADE API, configurations, and other systems rely on.

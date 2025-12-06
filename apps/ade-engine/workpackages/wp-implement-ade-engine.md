> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for implementing `ade_engine`.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update any TODOs directly in this file as you learn more.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.
> * When in doubt about behavior or naming, defer to:
>   * `apps/ade-engine/README.md`
>   * `apps/ade-engine/docs/01-engine-runtime.md` – runtime
>   * `apps/ade-engine/docs/02-config-and-manifest.md` – config
>   * `apps/ade-engine/docs/03-io-and-table-detection.md` – IO/extract
>   * `apps/ade-engine/docs/04-column-mapping.md` – mapping
>   * `apps/ade-engine/docs/05-normalization-and-validation.md` – normalize
>   * `apps/ade-engine/docs/06-artifact-json.md` – artifact
>   * `apps/ade-engine/docs/07-telemetry-events.md` – telemetry
>   * `apps/ade-engine/docs/08-hooks-and-extensibility.md` – hooks
>   * `apps/ade-engine/docs/09-cli-and-integration.md` – CLI
>   * `apps/ade-engine/docs/10-testing-and-quality.md` – tests
>
> **Naming rule:**  
> Use the terminology tables in the docs (`source_file`, `source_sheet`, `field`, etc.). Do **not** invent synonyms like “input file” in code or user‑facing strings.

---

## Work Package Checklist

Implementation order is intentionally **bottom‑up**, with tests at each layer.  
Keep short inline status notes as you go.

> **Definition of done (high‑level):**
> * Public API matches `README.md` + `01-engine-runtime.md`.
> * Artifact and telemetry schemas match `06-artifact-json.md` and `07-telemetry-events.md`.
> * Run a small end‑to‑end config + sample spreadsheet and get:
>   * `normalized.xlsx`,
>   * `artifact.json`,
>   * `events.ndjson`,
>   all consistent with the docs.

---

### 1. Core types, errors & schemas

**Goal:** Establish core runtime data structures and schema models that everything else depends on.

- [x] Implement core runtime types (`core/types.py`) per `01-engine-runtime.md` §3: initial dataclasses/enums in place.
  - `RunStatus`, `RunErrorCode`, `RunPhase`, `EngineInfo`
  - `RunRequest`, `RunPaths`, `RunContext`
  - `RunError`, `RunResult`
  - `ExtractedTable`, table indices & row index semantics
- [x] Implement column‑mapping and normalization types in `core/types.py`:
  - `ScoreContribution`, `MappedColumn`, `UnmappedColumn`, `ColumnMap`, `MappedTable` per `04-column-mapping.md`
  - `ValidationIssue`, `NormalizedTable` per `05-normalization-and-validation.md`
- [x] Implement engine error hierarchy (`core/errors.py`) per `01-engine-runtime.md` §3.3:
  - `AdeEngineError`
  - `ConfigError`, `InputError`, `HookError`, `PipelineError`
  - Helper to map exceptions → `RunError` (`RunErrorCode` + `RunPhase`), for use by `Engine.run`
- [x] Implement manifest schema models (`schemas/manifest.py`) + `ManifestContext` integration point per `02-config-and-manifest.md` §3:
  - `ManifestV1` + sub‑models (`ColumnsConfig`, `FieldConfig`, `WriterConfig`, `HookCollection`, etc.)
  - Ensure `ManifestV1.model_json_schema()` produces a usable JSON Schema (even if not wired yet)
- [x] Implement artifact schema models (`schemas/artifact.py`) per `06-artifact-json.md` §3–§6:
  - Top‑level `ArtifactV1` with `run`, `config`, `tables`, `notes`
  - Per‑table structures for header, mapped/unmapped columns, and validation issues
- [x] Implement telemetry schema models (`schemas/telemetry.py`) per `07-telemetry-events.md` §3:
  - `TelemetryEvent`, `TelemetryEnvelope`
  - Event names and levels (`run_started`, `run_completed`, `run_failed`, `pipeline_transition`, etc.)
- [x] Add basic schema tests (`tests/test_schemas_manifest.py`, `tests/test_schemas_artifact.py`, `tests/test_schemas_telemetry.py` or merge into existing schema‑focused tests):
  - Validate minimal valid objects
  - Assert key invariants (required fields, enum values, timestamp formats)

---

### 2. Config runtime

**Goal:** Load `ade_config`, parse the manifest into Python models, and build registries for column modules and hooks.

- [x] Implement `ManifestContext` (`config/manifest_context.py`) per `02-config-and-manifest.md` §3.2:
  - Wrap raw JSON + `ManifestV1`
  - Provide ergonomics: `.columns.order`, `.columns.fields`, `.writer`, `.hooks`
- [x] Implement config loader (`config/loader.py`) per `02-config-and-manifest.md` §4:
  - `load_config_runtime(package: str, manifest_path: Path | None)`:
    - Import `package` (default `"ade_config"`)
    - Resolve manifest path (override vs `<package>/manifest.json`)
    - Parse JSON → `ManifestV1`
    - Build `ManifestContext`
    - Build `ConfigRuntime` aggregate (manifest + column registry + hook registry)
- [x] Implement column registry (`config/column_registry.py`) per `02-config-and-manifest.md` §5:
  - `ColumnModule` (field, definition, module, detectors, transformer, validator)
  - `ColumnRegistry` keyed by canonical `field` name
  - Import each `field.module` (`ade_config.column_detectors.<field>`)
  - Discover:
    - `detect_*` callables
    - `transform` (optional)
    - `validate` (optional)
  - Validate signatures are keyword‑only and accept `**_` for forwards compatibility
- [x] Implement hook registry (`config/hook_registry.py`) per `02-config-and-manifest.md` §6 and `08-hooks-and-extensibility.md` §4–§5:
  - `HookStage` enum (`on_run_start`, `on_after_extract`, `on_after_mapping`, `on_before_save`, `on_run_end`)
  - `HookContext` dataclass per `08-hooks-and-extensibility.md` §5
  - `HookRegistry` mapping `HookStage` → ordered list of callables
  - Module resolution (`ade_config.hooks.*`), entrypoint selection (prefer `run`, fallback `main`)
- [x] Add unit tests for config runtime and manifest loading (`tests/test_config_loader.py`):
  - Happy path: minimal `ade_config` with simple manifest + column module + hook
  - Failure modes: missing manifest, invalid manifest, missing modules, bad signatures
  - Ensure config errors raise `ConfigError` and are correctly identified

---

### 3. IO & table detection

**Goal:** Turn `RunRequest` into concrete source files and `ExtractedTable` objects via streaming IO and row detectors.

- [x] Implement IO helpers (`infra/io.py`) per `03-io-and-table-detection.md` §3–§4:
  - `list_input_files(input_dir: Path) -> list[Path]`
    - Filter supported extensions (`.csv`, `.xlsx`, `.xlsm`, `.xltx`, `.xltm`)
    - Deterministic ordering
  - `iter_csv_rows(path: Path) -> Iterable[tuple[int, list]]`
    - UTF‑8 with BOM tolerance
    - Return 1‑based `row_index`
  - `iter_sheet_rows(path: Path, sheet_name: str) -> Iterable[tuple[int, list]]`
    - Use openpyxl `load_workbook(read_only=True, data_only=True)`
    - Normalize cell values into Python primitives (incl. `datetime`)
- [x] Implement row‑detector integration + table detection (`core/pipeline/extract.py`) per `03-io-and-table-detection.md` §5–§6:
  - Integrate `ade_config.row_detectors.*`:
    - Call all `detect_*` functions per row
    - Aggregate detector outputs into header/data scores
  - Implement heuristics to construct one or more `ExtractedTable` per sheet:
    - Detect header row
    - Identify contiguous data rows
    - Support multiple tables per sheet via `table_index`
  - Respect `RunRequest.input_files` vs `input_dir` and `input_sheets`
  - Emit `ExtractedTable` with correct `source_file`, `source_sheet`, row indices
- [x] Add unit tests for IO + extraction:
  - `tests/pipeline/test_io.py`: CSV/XLSX iteration, sheet filters, unsupported extensions
  - `tests/pipeline/test_extract.py`: simple detectors → predictable `ExtractedTable` boundaries, multiple tables per sheet, empty sheets/table‑missing behavior

---

### 4. Column mapping

**Goal:** Map physical columns in `ExtractedTable` to canonical fields defined in the manifest, and produce debuggable mapping metadata.

- [x] Ensure all column mapping data structures are in `core/types.py` per `04-column-mapping.md`:
  - `ScoreContribution`, `MappedColumn`, `UnmappedColumn`, `ColumnMap`, `MappedTable`
- [x] Implement mapping logic (`core/pipeline/mapping.py`) per `04-column-mapping.md` (“Mapping Pipeline”):
  - For each `ExtractedTable`:
    - Build per‑column samples (`column_values`, `column_values_sample`)
    - For each field/module:
      - Call all `detect_*` with the correct script API (1‑based `column_index`, `header`, samples, `ExtractedTable`, etc.)
      - Aggregate scores into `ScoreContribution`s
    - Choose the winning `(field, column)` mappings above the engine’s threshold
    - Generate `UnmappedColumn`s for remaining physical columns when manifest writer settings say so
  - Produce `MappedTable` from `ExtractedTable` + `ColumnMap`
- [x] Add unit tests for mapping scoring, thresholds, tie‑breaking (`tests/pipeline/test_mapping.py`):
  - Single clear winner per field
  - Ties resolved by manifest `columns.order`
  - Below‑threshold candidates → unmapped
  - `UnmappedColumn.output_header` generation is deterministic

---

### 5. Normalization & validation

**Goal:** Turn `MappedTable` into `NormalizedTable` (ordered matrix of values + validation issues) by running transforms and validators from `ade_config`.

- [x] Ensure normalization types are fully defined in `core/types.py`:
  - `ValidationIssue`, `NormalizedTable`
- [x] Implement transform + validate integration (`core/pipeline/normalize.py`) per `05-normalization-and-validation.md` §4–§5:
  - Build canonical row dict (`field` → raw value) per data row:
    - Use `MappedTable.column_map`, `ExtractedTable.data_rows`, and manifest `columns.order`
    - Use original sheet indices (`row_index`) for all downstream reporting
  - Transform phase:
    - Call `transform` (if present) per field in manifest order
    - Allow in‑place `row` mutation and/or returned update dicts
  - Validation phase:
    - Call `validate` (if present) per field after transforms
    - Collect issue dicts and convert to `ValidationIssue` (including `row_index`, `field`)
  - Build `NormalizedTable.rows`:
    - Canonical fields in `manifest.columns.order`
    - Extra unmapped columns appended in `UnmappedColumn` order
- [x] Add unit tests for normalization & validation (`tests/pipeline/test_normalize.py`):
  - Transform modifies values as expected
  - Validators produce `ValidationIssue` with correct `row_index`, `field`, `code`, `severity`
  - Edge cases: no data rows, unmapped fields (values `None` or defaults), cross‑field validation

---

### 6. Artifact & telemetry

**Goal:** Implement durable artifact output (`artifact.json`) and telemetry stream (`events.ndjson`) that match the documented contracts.

- [x] Implement artifact sink (`infra/artifact.py`) per `06-artifact-json.md` §1–§7:
  - `ArtifactSink` interface
  - `FileArtifactSink`:
    - `start(run, manifest)`, `record_table`, `note`, `mark_success`, `mark_failure`, `flush`
    - Atomic write pattern (`artifact.json.tmp` → `artifact.json`)
  - Ensure final JSON matches `ArtifactV1` schema:
    - `schema = "ade.artifact/v1"`
    - `run.status`, `run.error`, `run.outputs`, `tables`, `notes`
- [x] Implement telemetry sinks + envelope creation (`infra/telemetry.py`) per `07-telemetry-events.md` §2–§7:
  - `EventSink` protocol
  - `FileEventSink` writing NDJSON to `<logs_dir>/events.ndjson`
  - `DispatchEventSink` for fan‑out
  - `TelemetryConfig` and per‑run bindings (min level, sinks)
  - Build `TelemetryEnvelope` with `schema`, `version`, `run_id`, `timestamp`, `metadata`, `event`
- [x] Implement `PipelineLogger` facade per `07-telemetry-events.md` §6:
  - `note(...)` → artifact note (+ optional telemetry)
  - `event(name, ...)` → telemetry event only
  - `transition(phase, ...)` → standard `pipeline_transition` event
  - `record_table(...)` → artifact table entry (+ optional telemetry)
- [x] Add unit tests for artifact & telemetry:
  - `tests/test_artifact.py`:
    - Happy‑path success + failure artifacts
    - Invariants from `06-artifact-json.md` (“Behavior & invariants”)
  - `tests/test_telemetry.py`:
    - NDJSON is well‑formed, one envelope per line
    - Standard events (`run_started`, `run_completed`, `run_failed`, `pipeline_transition`) emitted at the right times

---

### 7. Hooks & extensibility

**Goal:** Allow `ade_config` to augment pipeline behavior via hooks at well‑defined stages.

- [x] Finalize `HookStage` enum and `HookContext` type per `08-hooks-and-extensibility.md` §2 & §5: context now mirrors documented fields.
- Ensure `HookContext` fields align with docs: `run`, `state`, `manifest`, `artifact`, `events`, `tables`, `workbook`, `result`, `logger`, `stage`
- [x] Wire hooks into pipeline phases per `08-hooks-and-extensibility.md` §6–§7: helper available; pipeline orchestrator still to hook up.
  - `on_run_start` after manifest + telemetry setup, before IO
  - `on_after_extract` after `ExtractedTable[]` built
  - `on_after_mapping` after `MappedTable[]` built
  - `on_before_save` after `NormalizedTable[]`, with live `Workbook`
  - `on_run_end` after `RunResult` computed (success or failure)
- [x] Ensure hook errors map to `HookError` and `RunErrorCode.HOOK_ERROR`:
  - A failing hook should fail the run with clear stage (`RunPhase.HOOKS`) and message
- [x] Add unit/integration tests around basic hook execution and error behavior:
  - Hooks run in configured order
- Hooks can mutate `state`, tables, and workbook as allowed
  - Exceptions in hooks cause runs to fail and are reflected in `artifact.json` + telemetry

---

### 8. Writer & workbook output

**Goal:** Use openpyxl to turn `NormalizedTable` into a normalized workbook, honoring writer settings and hooks.

- [x] Implement `write_workbook` (`core/pipeline/write.py`) using openpyxl per `05-normalization-and-validation.md` §6 and `README.md` “Excel support (openpyxl)”: 
  - Create an in‑memory `Workbook` (non‑streaming)
  - Decide sheet strategy:
    - Single combined sheet vs per‑table sheets (based on manifest writer config)
  - Write header row:
    - Canonical fields in `manifest.columns.order`
    - Extra `UnmappedColumn`s appended, with `output_header`
  - Append rows from `NormalizedTable.rows` in deterministic order:
    - By source file, sheet, table index
  - Invoke `on_before_save` hooks with `Workbook` and `NormalizedTable[]`
  - Save to `output_dir` (e.g. `normalized.xlsx`) and return `Path`
- [x] Ensure `on_before_save` hook receives a live `openpyxl.Workbook` per `05-normalization-and-validation.md` §6.3 and `08-hooks-and-extensibility.md` §6.3:
  - Hooks must **not** call `workbook.save()`; engine owns save/close
- [x] Add unit tests verifying header order, sheet naming, and openpyxl integration (`tests/pipeline/test_write.py`):
  - Header ordering and extra column placement
  - Stable sheet names and row ordering
  - `on_before_save` can decorate workbook (e.g. add a summary sheet)

---

### 9. Engine orchestration & CLI

**Goal:** Implement the main `Engine` runtime, connect all pipeline stages, and expose a CLI that mirrors `RunResult`.

- [x] Implement `Engine` and `run()` public API (`core/engine.py`, `ade_engine/__init__.py`) per `README.md` and `01-engine-runtime.md` §1–§2:
  - `Engine.run(request: RunRequest) -> RunResult`
    - Validate `RunRequest` invariants (exactly one of `input_files`/`input_dir`)
    - Build `RunPaths`, create directories
    - Create `RunContext` with fresh `state`, `RunPhase.INITIALIZATION`
    - Load config runtime (`load_config_runtime`)
    - Bind artifact + telemetry sinks
    - Orchestrate pipeline via `execute_pipeline(...)`
    - Run hooks at appropriate stages
    - Map exceptions to `RunError` with correct `RunErrorCode` + `RunPhase`
  - Top‑level `run(*args, **kwargs)` helper that constructs `RunRequest` and uses a short‑lived `Engine`
  - Export `Engine`, `run`, `RunRequest`, `RunResult`, `EngineInfo`, `RunStatus`, `__version__` from `ade_engine/__init__.py`
- [x] Implement pipeline orchestrator (`core/pipeline/pipeline_runner.py`) per `01-engine-runtime.md` §4 and `03/04/05` docs:
  - `execute_pipeline(ctx, cfg, logger) -> (list[NormalizedTable], tuple[Path, ...])`
  - Phase transitions:
    - `EXTRACTING` → `extract_tables`
    - `MAPPING` → `map_table`
    - `NORMALIZING` → `normalize_table`
    - `WRITING_OUTPUT` → `write_workbook`
    - `COMPLETED` vs `FAILED`
  - Emit `pipeline_transition` telemetry events via `PipelineLogger`
- [x] Implement CLI (`cli/app.py`, `cli/commands/run.py`, `cli/commands/version.py`, `__main__.py`) per `09-cli-and-integration.md`:
  - `ade-engine run`:
    - Flags → `RunRequest` (`--input`, `--input-dir`, `--input-sheet`, `--output-dir`/`--output-file`, `--logs-dir`/`--logs-file`, `--config-package` (module or path))
    - Run engine once
    - Emit NDJSON events to stdout (parse `engine.complete` for status and artifacts)
    - Set exit code 0 on success, non‑zero on failure / usage error
  - `ade-engine version`:
    - Print engine `__version__`
    - Optionally include manifest version when `--manifest-path` is supplied
  - `python -m ade_engine` → `cli.app()`
- [x] Add tests for `Engine.run` and CLI JSON output:
  - `tests/test_engine_runtime.py`:
    - Happy path using a minimal temp `ade_config`
    - Failure modes: config error, input error, hook error, pipeline error
  - `tests/test_cli.py`:
    - `subprocess` call to `python -m ade_engine run ...`
    - Validate NDJSON event output and exit codes (single and multi-input)

---

### 10. End‑to‑end & regression tests

**Goal:** Verify the full engine behavior with a real `ade_config`, sample inputs, and guard contracts against regressions.

- [x] Implement fixtures for temp `ade_config` packages + sample inputs per `10-testing-and-quality.md` §3 (`tests/fixtures/`):
  - `config_factories.py`:
    - Helpers to create minimal `ade_config` with:
      - `manifest.json`
      - one or two `column_detectors` modules
      - simple row detectors
      - basic hooks (optional)
  - `sample_inputs.py`:
    - Helpers to create small CSV and XLSX examples (single + multi‑sheet)
- [x] Add end‑to‑end tests (Python API + CLI) verifying artifact + events + workbook shape (`tests/test_engine_runtime.py`, `tests/test_cli.py`):
  - Run engine with temp config + sample input
  - Assert:
    - `RunResult.status == "succeeded"`
    - Output workbook exists and is a valid XLSX
    - `artifact.json` matches schema and has at least one table
    - `events.ndjson` contains lifecycle events
- [x] Add mapping stability / artifact contract tests per `10-testing-and-quality.md` §6:
  - Capture snapshot of `artifact.tables[*].mapped_columns` for a known config+input
  - Re‑run and compare snapshot to detect unintended mapping changes
  - Validate artifact invariants (`run.status`, non‑empty outputs on success, etc.)
- [x] Add large‑input smoke tests (basic performance) per `10-testing-and-quality.md` §7:
  - Generate a large CSV/XLSX (e.g., ≥50k rows) with minimal config
  - Run engine and ensure:
    - It completes without error
    - Memory/time remain within acceptable bounds (coarse checks only)

### 11. Upcoming ade-api and ade-web follow-ups

**Goal:** Prepare integration tasks for backend and frontend now that the engine runtime is complete.

- [x] Update `apps/ade-api` run orchestration to invoke the new engine CLI/`Engine.run` API, wiring artifact/events paths into run records. (CLI args + run summary wired)
- [x] Extend `apps/ade-api` schemas and responses to surface `artifact.json` and telemetry event locations returned by the engine.
- [x] Teach `apps/ade-api` build/venv flow to bundle the new end-to-end configuration fixtures or equivalent sample configurations for sandbox runs. *(Added a sandbox template mirroring the engine E2E fixtures for quick smoke tests.)*
- [x] Update `apps/ade-web` screens to display run artifacts and telemetry summaries, including mapped/unmapped columns and validation issues.
- [x] Add frontend API bindings for any new backend fields (artifact/events paths) and render download links in the run detail UI.
- [x] Document the available config templates (default + sandbox) and provide a sandbox quickstart in the backend docs/README once the UI surfaces them.
- [x] Evaluate and refactor the `apps/ade-api` run worker path to reuse the new engine orchestration (reduce duplication with `RunsService` now that engine integration is complete).
  - Refactored `RunsService.execute_run` to consume `RunsService` run stream frames directly, update run state from the completion event (including artifact/log/output URIs), and only fall back to run reconciliation when the stream is unavailable.
- [x] Tidy `apps/ade-api` run-service imports so logging is initialized alongside the other stdlib dependencies used for the module logger.
- [x] Ensure the Documents screen uses the run routes to load artifacts, telemetry, and outputs for the latest run so engine results surface in the drawer.

> Note: The default `ade-api` config template now uses the v1 manifest shape (relative module paths) and the engine exports the telemetry event JSON schema for `ade-web` imports.

> **Agent note:**  
> If you discover missing types, invariants, or behavior while implementing, **add checklist items here** and reference the relevant `docs/*.md` section before changing code.

---

# Workpackage: Implement `ade_engine` Runtime

## 1. Objective

**Goal:**  
Implement the `ade_engine` runtime (core engine, pipeline, config integration, artifact/telemetry, CLI) exactly as specified by the documentation under `apps/ade-engine/docs/` and `apps/ade-engine/README.md`.

You will:

* Implement the **core runtime types and pipeline** (`RunRequest`, `RunContext`, `RunResult`, `ExtractedTable`, `MappedTable`, `NormalizedTable`) per `01-engine-runtime.md`, `03-io-and-table-detection.md`, `04-column-mapping.md`, and `05-normalization-and-validation.md`.
* Implement the **config runtime** (`config` loader, manifest schema, column + hook registries) per `02-config-and-manifest.md`.
* Implement **IO, mapping, normalization, artifact, telemetry, hooks, and CLI** in a test‑driven, layered way per `03–10` docs.

The result should:

* Match the documented architecture and contracts for:
  * runtime API (`Engine`, `run()`, `RunRequest`, `RunResult`, `RunStatus`, `RunPhase`, errors),
  * artifact (`artifact.json`) and telemetry (`events.ndjson`) schemas,
  * script APIs in `ade_config` (detectors, transforms, validators, hooks).
* Be covered by unit + integration tests as described in `10-testing-and-quality.md`, with deterministic behavior for given configurations and inputs.

---

## 2. Context (What you are starting from)

We already have detailed design docs and naming conventions; this workpackage is about implementing code to match them.

### Current state

* Architecture, terminology, and desired module layout are defined in:
  * `apps/ade-engine/README.md` – high‑level architecture, terminology, target package layout.
  * `apps/ade-engine/docs/README.md` – chapter index and recommended reading order.
* Conceptual behavior for each subsystem is documented:
  * Runtime & core types — `01-engine-runtime.md`.
  * Config & manifest — `02-config-and-manifest.md`.
  * IO & table detection — `03-io-and-table-detection.md`.
  * Column mapping — `04-column-mapping.md`.
  * Normalization & validation — `05-normalization-and-validation.md`.
  * Artifact JSON — `06-artifact-json.md`.
  * Telemetry events — `07-telemetry-events.md`.
  * Hooks & extensibility — `08-hooks-and-extensibility.md`.
  * CLI & integration — `09-cli-and-integration.md`.
  * Testing & quality — `10-testing-and-quality.md`.

### Existing structure (desired, mostly not implemented yet)

See `apps/ade-engine/README.md` “Package layout (layered and obvious)” and `docs/README.md`:

* `ade_engine/core/` — runtime orchestrator + pipeline (`engine.py`, `types.py`, `pipeline/`).
* `ade_engine/config/` — config loader + manifest/registry glue (legacy name: `config_runtime`).
* `ade_engine/infra/` — IO, artifact, telemetry.
* `ade_engine/schemas/` — Pydantic models for manifest, artifact, telemetry.
* `ade_engine/cli/` — Typer‑based CLI wiring.
* `ade_engine/__init__.py` — narrow public API: `Engine`, `run`, `RunRequest`, `RunResult`, `RunStatus`, `EngineInfo`, `__version__`.

### Known constraints & contracts

* Terminology and naming in code must align with the tables in each doc; e.g. `source_file`, `source_sheet`, `field`, `RunStatus`, `RunPhase` etc.
* Config packages (`ade_config`) are the only place for **business logic**; engine must remain generic (`README.md` “Big picture” and `02-config-and-manifest.md` §1).
* Artifact and telemetry formats are treated as **contracts** per `06-artifact-json.md` and `07-telemetry-events.md`.
* Testing strategy and folder layout are prescribed in `10-testing-and-quality.md` and should be followed.
* `Engine` is **logically stateless**; all per‑run state lives on `RunContext`.

---

## 3. Target architecture / structure (ideal)

See `apps/ade-engine/README.md` “Package layout (layered and obvious)”. This workpackage assumes the following structure:

```text
apps/ade-engine/
  ade_engine/
    __init__.py          # public API: Engine, run, RunRequest, RunResult, RunStatus, EngineInfo, __version__
    __main__.py          # `python -m ade_engine` → cli.app()

    core/
      __init__.py        # re-export Engine, RunRequest, RunResult, RunStatus, core types
      engine.py          # Engine.run orchestration per 01-engine-runtime.md §4
      types.py           # RunRequest, RunResult, RunContext, RunPaths, ExtractedTable, MappedTable, NormalizedTable, enums
      errors.py          # AdeEngineError + config/input/hook/pipeline errors → RunErrorCode
      pipeline/
        __init__.py      # re-export execute_pipeline, phase helpers
        extract.py       # IO + ExtractedTable detection per 03-io-and-table-detection.md
        mapping.py       # column mapping per 04-column-mapping.md
        normalize.py     # transforms + validators per 05-normalization-and-validation.md
        write.py         # workbook writing per 05-normalization-and-validation.md §6
        pipeline_runner.py # execute_pipeline() orchestration and RunPhase transitions

    config/              # config runtime (formerly config_runtime/)
      __init__.py
      loader.py          # load_config_runtime per 02-config-and-manifest.md §4
      manifest_context.py# ManifestContext wrapper per 02-config-and-manifest.md §3.2
      column_registry.py # ColumnModule / ColumnRegistry per 02-config-and-manifest.md §5
      hook_registry.py   # HookRegistry, HookContext, HookStage per 02-config-and-manifest.md §6 and 08-hooks-and-extensibility.md

    infra/               # IO + artifact + telemetry plumbing
      __init__.py
      io.py              # list_input_files, iter_csv_rows, iter_sheet_rows per 03-io-and-table-detection.md
      artifact.py        # ArtifactSink, FileArtifactSink per 06-artifact-json.md
      telemetry.py       # EventSink, FileEventSink, DispatchEventSink, TelemetryConfig, PipelineLogger per 07-telemetry-events.md

    schemas/             # Pydantic models (Python-first schemas)
      __init__.py
      manifest.py        # ManifestV1 and friends per 02-config-and-manifest.md §3
      artifact.py        # Artifact schema per 06-artifact-json.md §3–§7
      telemetry.py       # TelemetryEnvelope, TelemetryEvent per 07-telemetry-events.md §3

    cli/
      __init__.py
      app.py             # Typer app exposing `ade-engine` per 09-cli-and-integration.md
      commands/
        run.py           # main run command; builds RunRequest and prints JSON summary
        version.py       # prints engine version (and maybe manifest version)

  docs/                  # existing docs (do not modify structurally as part of this workpack)
    ...

  tests/
    pipeline/
      test_io.py
      test_extract.py
      test_mapping.py
      test_normalize.py
      test_write.py
    test_engine_runtime.py
    test_config_loader.py
    test_artifact.py
    test_telemetry.py
    test_cli.py
    fixtures/
      __init__.py
      config_factories.py  # helpers to create temp ade_config packages
      sample_inputs.py     # helpers to generate CSV/XLSX fixtures
````

> **Agent instruction:**
>
> * Keep this section in sync with reality as you implement.
> * If the design or file layout changes, update this section and the checklist **before** editing code.

# Logical module layout (source -> sections below):
# - apps/ade-engine/README.md - ADE Engine (Runtime)
# - apps/ade-engine/docs/01-engine-runtime.md - ADE Engine Runtime
# - apps/ade-engine/docs/02-config-and-manifest.md - Config Runtime & Manifest
# - apps/ade-engine/docs/03-io-and-table-detection.md - IO and Table Detection
# - apps/ade-engine/docs/04-column-mapping.md - 04 — Column Mapping
# - apps/ade-engine/docs/05-normalization-and-validation.md - Normalization & Validation
# - apps/ade-engine/docs/06-artifact-json.md - Artifact JSON (`artifact.json`)
# - apps/ade-engine/docs/07-telemetry-events.md - Telemetry Events
# - apps/ade-engine/docs/08-hooks-and-extensibility.md - Hooks & Extensibility
# - apps/ade-engine/docs/09-cli-and-integration.md - CLI and Integration with ADE API
# - apps/ade-engine/docs/10-testing-and-quality.md - Testing & Quality
# - apps/ade-engine/docs/README.md - ADE Engine – Detailed Documentation Index

# apps/ade-engine/README.md
```markdown
# ADE Engine (Runtime)

The **ADE engine** is a config‑driven runtime that turns messy spreadsheets into
a **normalized Excel workbook plus a full audit artifact**.

You can think of it as:

> “Run a pipeline over spreadsheets using an `ade_config` plugin that defines how to detect, map, transform and validate data.”

This document describes the **architecture**, **folder structure**, **core types**, and
**script APIs** you need to understand to implement or extend the engine.

---

## 1. Big picture

At runtime, inside a **pre‑built virtual environment**:

1. The engine loads a versioned **config package** (`ade_config`) with:
   - a JSON/YAML **manifest** (fields, writer settings, hooks, env)
   - **row detectors** (table finding)
   - **column detectors** (field recognition)
   - **transforms** & **validators**
   - **hooks** (lifecycle callbacks)
2. It **reads spreadsheets** (CSV/XLSX) in streaming mode.
3. It **detects tables**, **maps columns** to canonical fields, and
   **normalizes** values row‑by‑row using the config code.
4. It emits:
   - a normalized **`output.xlsx`** workbook
   - an **`artifact.json`** (human/audit readable)
   - an **`events.ndjson`** telemetry stream.

The engine itself is **business‑logic free**: all domain rules live in `ade_config`.

In production, the ADE API:

- builds a **frozen venv** per config (`ade_engine` + a specific `ade_config` version),
- then, for each **job**, launches a worker (process or thread) inside that venv,
- and calls the engine with **file paths** (input / output / logs).

From the engine’s perspective, it just runs synchronously inside an isolated environment
with `ade_config` installed; **job IDs and workspace concepts are handled entirely by the backend**.

---

### 1.1 Runtime & virtual environments

The deployment model is:

- **Build time (outside the engine)**  
  - ADE backend creates a venv for `<config_id>/<build_id>`.
  - Installs `ade_engine` and the selected `ade_config`.
  - Optionally pins dependencies and writes a `packages.txt` for reproducibility.

- **Run time (inside the venv)**  
  - Backend dispatches a job to a worker (thread/process/container).  
  - Worker activates that venv and invokes the engine with explicit paths:

    ```bash
    # Typical worker invocation from the ADE API
    /path/to/.venv/<config_id>/<build_id>/bin/python \
      -m ade_engine \
      --input /data/jobs/<job_id>/input/input.xlsx \
      --output-dir /data/jobs/<job_id>/output \
      --logs-dir /data/jobs/<job_id>/logs
    ```

  - The engine:
    - reads `input.xlsx` (or multiple inputs, if provided),
    - imports `ade_config` and reads its `manifest.json`,
    - runs the pipeline once for that call,
    - writes `normalized.xlsx`, `artifact.json`, `events.ndjson` to the given output/logs dirs.

The **engine does not know or care about job IDs**. It only needs:

- the config to use (`config_package`, `manifest_path`),
- one or more **input files**,
- where to write outputs and logs.

The ADE API is responsible for mapping those paths back to a job record in its own database.

The engine has **no knowledge** of:

- the ADE API,
- workspaces, config package registry, or queues,
- job IDs,
- how many threads/processes are running.

It is a pure “input files → normalized workbook + logs” component.

---

## 2. Package layout

The `ade_engine` package is organized by responsibility, using standard Python conventions.

```text
ade_engine/
  __init__.py          # Public API: Engine, run(), RunRequest, RunResult, __version__
  __main__.py          # `python -m ade_engine` → cli.main()

  engine.py            # Engine class + high-level run() orchestration
  types.py             # Shared dataclasses (RunRequest, RunResult, RunContext, tables, enums)
  config_runtime.py    # Load manifest, detectors, transforms, validators, hooks from ade_config
  io.py                # CSV/XLSX IO: list_input_files, iter_sheet_rows, etc.
  hooks.py             # HookStage enum + HookRegistry + HookContext
  artifact.py          # ArtifactSink + FileArtifactSink + ArtifactBuilder (artifact.json)
  telemetry.py         # TelemetryConfig, TelemetryBindings, event sinks, PipelineLogger
  cli.py               # CLI entrypoint (args parsing, JSON output / error codes)

  pipeline/
    __init__.py        # Re-exports execute_pipeline() and stage helpers
    extract.py         # Use IO + row detectors to find tables → RawTable[]
    mapping.py         # Column detectors → ColumnMapping/ExtraColumn per table
    normalize.py       # Transforms + validators → NormalizedTable + ValidationIssue[]
    write.py           # Compose normalized tables into Excel workbook(s)
    pipeline.py        # PipelineRunner: orchestrates phases & transitions

  schemas/
    __init__.py
    manifest.py        # Pydantic models for config manifest + JSON schema generator
    telemetry.py       # Pydantic models for telemetry envelopes + JSON schema generator

````

If you know this tree, you know where everything lives:

* **“How do I run the engine?”** → `engine.py`, `__init__.py`
* **“How do we load config scripts?”** → `config_runtime.py`
* **“How do we read Excel/CSV?”** → `io.py`
* **“How does the pipeline work?”** → `pipeline/`
* **“Where is artifact/telemetry written?”** → `artifact.py`, `telemetry.py`
* **“What does the manifest look like?”** → `schemas/manifest.py` (Python models)
  (JSON schemas can be generated from these models for external validation)

Config packages live separately and look like:

```text
ade_config/
  __init__.py
  manifest.json
  row_detectors/
    __init__.py
    header.py
    data.py
  column_detectors/
    __init__.py
    member_id.py
    email.py
    ...
  hooks/
    __init__.py
    on_run_start.py
    on_after_extract.py
    on_after_mapping.py
    on_before_save.py
    on_run_end.py
  _shared.py
```

---

## 3. Core runtime types (`types.py`)

### 3.1 Run-level types

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

RunStatus = Literal["succeeded", "failed"]
```

**EngineMetadata**

```python
@dataclass(frozen=True)
class EngineMetadata:
    name: str = "ade-engine"
    version: str = "0.0.0"
    description: str | None = None
```

**RunRequest**

What callers pass in when they run the engine programmatically:

```python
@dataclass
class RunRequest:
    # Config
    config_package: str = "ade_config"
    manifest_path: Path | None = None   # override manifest.json if provided

    # Inputs (one of the two is required; providing both is an error)
    input_files: Sequence[Path] | None = None  # preferred: explicit files, typically [Path("input.xlsx")]
    input_root: Path | None = None             # optional: scan folder for CSV/XLSX

    # Optional sheet filtering (XLSX only; CSV has a single implicit sheet)
    input_sheets: Sequence[str] | None = None  # restrict to specific sheet names

    # Output / logs
    output_root: Path | None = None           # folder for normalized.xlsx
    logs_root: Path | None = None             # folder for artifact.json + events.ndjson

    # Execution options
    safe_mode: bool = False
    metadata: Mapping[str, Any] | None = None  # arbitrary tags (job_id, workspace_id, etc.)
```

The engine requires **exactly one** of `input_files` or `input_root`. If both are provided,
it fails fast with a `ValueError` rather than guessing.

In the simplest case, the ADE API:

* resolves the job’s primary input file (e.g. `/data/jobs/<job_id>/input/input.xlsx`),
* chooses output/logs dirs (e.g. `/data/jobs/<job_id>/output` and `/data/jobs/<job_id>/logs`),
* and calls:

```python
RunRequest(
    config_package="ade_config",
    input_files=[Path("/data/jobs/<job_id>/input/input.xlsx")],
    output_root=Path("/data/jobs/<job_id>/output"),
    logs_root=Path("/data/jobs/<job_id>/logs"),
    metadata={"job_id": "<job_id>", "config_id": "<config_id>"},
)
```

The engine doesn’t know what `job_id` means; it just surfaces metadata into artifact/telemetry.

`safe_mode` is a hint that the caller wants a more conservative execution (e.g. disable
optional integrations or network‑using sinks). OS‑level resource limits (CPU, memory, network)
are still enforced by the worker environment, not by the engine itself.

**RunResult**

What the engine returns:

```python
@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    error: str | None
    output_paths: tuple[Path, ...]      # normalized workbooks (usually length 1)
    artifact_path: Path                 # audit JSON
    events_path: Path                   # telemetry NDJSON
    processed_files: tuple[str, ...]    # input file names as seen by the engine
```

**RunPaths**

Resolved filesystem layout for a run:

```python
@dataclass(frozen=True)
class RunPaths:
    input_root: Path
    output_root: Path
    logs_root: Path
    artifact_path: Path       # logs_root / "artifact.json"
    events_path: Path         # logs_root / "events.ndjson"
```

* If you pass `output_root`/`logs_root`, those are used directly.
* If you only pass `input_files`, the engine infers defaults (e.g. sibling `output` / `logs`
  folders next to the first input file).
* If you only pass `input_root`, the engine infers defaults relative to that directory
  (e.g. `input_root.parent / "output"` and `input_root.parent / "logs"`).
* It is an error to provide both `input_files` and `input_root`.

**RunContext**

Internal context shared across pipeline, hooks, and telemetry:

```python
@dataclass
class RunContext:
    run_id: str                 # generated UUID or similar per run
    metadata: dict[str, Any]    # includes caller-supplied metadata
    manifest: ManifestContext   # see config_runtime
    env: dict[str, str]         # manifest.env
    paths: RunPaths
    started_at: datetime
    safe_mode: bool
    state: dict[str, Any] = field(default_factory=dict)  # per-run scratch space for scripts
```

`RunContext.state` is **per run**: each call to `Engine.run()` gets a fresh dict which
detectors, transforms, validators, and hooks can share during that run. It is never
shared across runs.

The ADE backend may include a `job_id` inside `metadata`, but the engine just treats it as
opaque metadata.

Because all per‑run state lives on `RunContext` and not on the `Engine` instance itself,
the `Engine` class is **logically stateless** and can be safely reused across requests or
threads (as long as each call uses a fresh `RunRequest`).

### 3.2 Table and pipeline types

These types model tables and mapping/normalization results.

```python
@dataclass
class RawTable:
    source_file: Path
    source_sheet: str | None
    header_row: list[str]
    data_rows: list[list[Any]]
    header_index: int         # 1-based row index in original sheet
    first_data_index: int     # 1-based
    last_data_index: int      # 1-based
```

Column mapping:

```python
@dataclass
class ScoreContribution:
    field: str                # canonical field
    detector: str             # "module.func"
    delta: float

@dataclass
class ColumnMapping:
    field: str                # canonical field name
    header: str               # original header text
    index: int                # 0-based input column index
    score: float
    contributions: tuple[ScoreContribution, ...]
```

Unmapped columns:

```python
@dataclass
class ExtraColumn:
    header: str
    index: int                # 0-based input column index
    output_header: str        # "raw_<safe_name>"
```

Mapped and normalized tables:

```python
@dataclass
class MappedTable:
    raw: RawTable
    mapping: list[ColumnMapping]
    extras: list[ExtraColumn]

@dataclass
class ValidationIssue:
    row_index: int            # original sheet row index (1-based)
    field: str                # canonical field
    code: str                 # machine-readable code
    severity: str             # "error", "warning", ..."
    message: str | None
    details: dict[str, Any] | None

@dataclass
class NormalizedTable:
    mapped: MappedTable
    rows: list[list[Any]]            # rows in manifest.order + extras
    issues: list[ValidationIssue]
    output_sheet_name: str
```

`PipelinePhase` is an enum (`INITIALIZED`, `EXTRACTING`, `MAPPING`, `NORMALIZING`, `WRITING_OUTPUT`, `COMPLETED`, `FAILED`) used by telemetry.

---

## 4. Config packages (`ade_config`) and manifest

The engine expects an **`ade_config`** Python package installed in the same environment.

Typical layout:

```text
ade_config/
  __init__.py
  manifest.json              # config manifest consumed by ade_engine
  row_detectors/
    __init__.py
    header.py                # detect_* functions voting for header rows
    data.py                  # detect_* functions voting for data rows
  column_detectors/
    __init__.py
    member_id.py             # detectors + transform + validate for a field
    email.py
    ...
  hooks/
    __init__.py
    on_run_start.py          # optional hooks called by the engine
    on_after_extract.py
    on_after_mapping.py
    on_before_save.py
    on_run_end.py
  _shared.py                 # optional shared helpers
```

### 4.1 Manifest schema (Python-first)

The manifest is still stored as JSON (or optionally TOML/YAML), but the engine’s **source of truth**
is a set of Python models in `ade_engine.schemas.manifest` (e.g. a Pydantic `ManifestV1`).

At startup the engine:

1. Reads `manifest.json` from the `ade_config` package (or from `manifest_path` if overridden).
2. Loads it into `ManifestV1` (Pydantic).
3. Uses helper methods on `ManifestContext` for convenient access (column order, column meta, defaults, writer config, env).

For **external validation or documentation**, the engine can emit JSON Schema via
`ManifestV1.model_json_schema()` into a generated file (e.g. `manifest_v1.schema.json`),
but that JSON is derived from the Python models, not hand-maintained.

Conceptually the manifest looks like:

```jsonc
{
  "config_script_api_version": "1",
  "info": {
    "schema": "ade.manifest/v1.0",
    "title": "My Config",
    "version": "1.2.3",
    "description": "Optional"
  },
  "env": {
    "LOCALE": "en-CA",
    "DATE_FMT": "%Y-%m-%d"
  },
  "engine": {
    "defaults": {
      "timeout_ms": 180000,
      "memory_mb": 384,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.35,
      "detector_sample_size": 64
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_",
      "output_sheet": "Normalized"
    }
  },
  "hooks": {
    "on_run_start":     [{ "script": "hooks/on_run_start.py" }],
    "on_after_extract": [{ "script": "hooks/on_after_extract.py" }],
    "on_after_mapping": [{ "script": "hooks/on_after_mapping.py" }],
    "on_before_save":   [{ "script": "hooks/on_before_save.py" }],
    "on_run_end":       [{ "script": "hooks/on_run_end.py" }]
  },
  "columns": {
    "order": ["member_id","email","..."],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "script": "column_detectors/member_id.py",
        "required": true,
        "enabled": true,
        "synonyms": ["member id", "member#"],
        "type_hint": "string"
      },
      "email": {
        "label": "Email",
        "script": "column_detectors/email.py",
        "required": true,
        "type_hint": "string"
      }
    }
  }
}
```

`config_runtime.py` turns this into a typed `ManifestContext` with helpers:
`column_order`, `column_meta`, `defaults`, `writer`, `env`.

---

## 5. How the engine runs

### 5.1 Public API (`__init__.py` + `engine.py`)

The main entry points:

```python
from pathlib import Path
from ade_engine import Engine, run, RunRequest

# Simple: one input file, explicit output/logs
engine = Engine()
result = engine.run(
    RunRequest(
        input_files=[Path("input.xlsx")],
        output_root=Path("output"),
        logs_root=Path("logs"),
    )
)

# Convenience helper: sugar over Engine.run
result = run(
    input_files=[Path("input.xlsx")],
    output_root=Path("output"),
    logs_root=Path("logs"),
)
```

`Engine` is **logically stateless**: it does not keep any mutable per‑run data on the instance.
Each call to `run()` constructs a fresh `RunContext` and `state` dict. You can safely reuse a
single `Engine` across threads or requests as long as each call uses its own `RunRequest`.

Under the hood, `Engine.run()`:

1. Normalizes a `RunRequest` into `RunPaths` and `RunContext`:

   * chooses `input_root` (from files or explicit folder),
   * chooses `output_root` and `logs_root` (from request or defaults based on input),
   * generates a `run_id`,
   * seeds `metadata` and a shared `state` dict.
2. Calls `load_config_runtime()` to load the manifest, column detectors, row detectors, and hooks.
3. Binds telemetry sinks (`TelemetryConfig.bind`) and creates a `PipelineLogger`.
4. Calls `ON_RUN_START` hooks.
5. Calls `execute_pipeline()` in `pipeline/pipeline.py`:

   * `extract_tables` → `RawTable[]`
   * `map_table` per table → `MappedTable`
   * `normalize_table` per table → `NormalizedTable`
   * `write_workbook` → `output.xlsx`
6. Marks the artifact as success/failure and calls `ON_RUN_END` hooks.
7. Returns a `RunResult`.

The engine is single‑run and synchronous: **one call → one pipeline run**. Concurrency
across jobs is handled by the ADE API / worker framework, which:

* looks up the job record,
* resolves input/output/log paths,
* then calls `Engine.run()` (or the CLI) in the appropriate venv.

### 5.2 How the ADE backend typically uses the engine

A typical integration in the ADE backend looks like:

1. Request comes in: “run config `<config_id>` on uploaded file `<document_id>`”.

2. Backend:

   * ensures a venv exists for `<config_id>/<build_id>` with `ade_engine` + `ade_config` installed,
   * resolves the document path and creates a job folder with `input/`, `output/`, `logs/`.

3. Backend enqueues a worker task that:

   * activates the config-specific venv,
   * invokes the engine via CLI or API:

     ```python
     from ade_engine import run

     result = run(
         config_package="ade_config",
         input_files=[Path(f"/data/jobs/{job_id}/input/input.xlsx")],
         output_root=Path(f"/data/jobs/{job_id}/output"),
         logs_root=Path(f"/data/jobs/{job_id}/logs"),
         metadata={"job_id": job_id, "config_id": config_id},
     )
     ```

4. Backend stores `RunResult` info and/or parses `artifact.json` and `events.ndjson`
   to update job status, reports, etc.

The engine has **no idea** that a “job” exists; it only sees file paths and metadata.

---

## 6. Pipeline stages (`pipeline/`)

### 6.1 `extract.py` – find tables from raw sheets

Responsible for:

* Listing input files (`io.list_input_files`) if `input_root` is used,
* Or using the explicit `input_files` provided.
* For each CSV/XLSX:

  * Iterate rows using `io.iter_sheet_rows`
  * Run row detectors (if configured) to score header/data rows
  * Decide table boundaries (header row, first/last data row)
  * Materialize `RawTable` objects

API:

```python
def extract_tables(
    ctx: RunContext,
    cfg: ConfigRuntime,
    logger: PipelineLogger,
) -> list[RawTable]:
    ...
```

`input_sheets` (if provided) are applied to XLSX workbooks to restrict processing to a
subset of sheet names. CSV inputs are treated as a single implicit sheet; sheet filters
have no effect on them.

### 6.2 `mapping.py` – map raw columns to canonical fields

For each `RawTable`:

1. Build `column_values` and `column_values_sample` per column.
2. For each column and each field:

   * Call all `detect_*` functions in the field’s script with:

     * `job`, `state`, `field_name`, `field_meta`, `header`,
       `column_values_sample`, `column_values`, `table`, `column_index`,
       `manifest`, `env`, `logger`
3. Aggregate scores per field and record `ScoreContribution`s.
4. Pick the best field above the manifest’s `mapping_score_threshold`.
5. If no match and `append_unmapped_columns` is true, create `ExtraColumn`.

API:

```python
def map_table(
    ctx: RunContext,
    cfg: ConfigRuntime,
    raw: RawTable,
    logger: PipelineLogger,
) -> MappedTable:
    ...
```

After all tables have been mapped, the engine invokes any `on_after_mapping` hooks,
passing the list of `MappedTable` objects. This is the ideal place for configs to:

* tweak or correct mappings,
* reorder or drop fields,
* adjust `extras`,

before normalization begins.

### 6.3 `normalize.py` – transforms & validators

For each `MappedTable`:

1. Build a `canonical_row` dict for each raw row, keyed by field.

2. Run `transform` for each field module (if present):

   ```python
   def transform(
       *,
       job,
       state: dict,
       row_index: int,
       field_name: str,
       value,
       row: dict,                   # canonical row dict (field -> value)
       field_meta: dict | None,
       manifest: dict,
       env: dict | None,
       logger,
       **_,
   ) -> dict | None:
       ...
   ```

3. Run `validate` for each field module (if present):

   ```python
   def validate(
       *,
       job,
       state: dict,
       row_index: int,
       field_name: str,
       value,
       row: dict,
       field_meta: dict | None,
       manifest: dict,
       env: dict | None,
       logger,
       **_,
   ) -> list[dict]:
       # Return issue dicts: {"code": "invalid_format", "severity": "error", ...}
       ...
   ```

4. Build normalized rows and `ValidationIssue` objects.

API:

```python
def normalize_table(
    ctx: RunContext,
    cfg: ConfigRuntime,
    mapped: MappedTable,
    logger: PipelineLogger,
) -> NormalizedTable:
    ...
```

### 6.4 `write.py` – write the workbook

Given one or more `NormalizedTable`s:

* Determine whether to:

  * write a single combined output sheet (`writer.output_sheet`) or
  * one sheet per normalized table (deduplicating sheet names).

  In combined mode, normalized rows are appended in a deterministic order:
  by input file name, then by sheet order within that file, then by table
  detection order.

* Build header rows from `manifest.columns.order` and column labels.

* Append normalized rows (canonical fields + extra columns).

* Invoke `on_before_save` hook (if configured) with the openpyxl `Workbook`.

* Save workbook to a temp path, then atomically move to `output_root/normalized.xlsx`.

API:

```python
def write_workbook(
    ctx: RunContext,
    cfg: ConfigRuntime,
    tables: list[NormalizedTable],
) -> Path:
    ...
```

### 6.5 `pipeline.py` – orchestrate phases

`PipelineRunner` coordinates the stages and phase transitions:

```python
def execute_pipeline(
    ctx: RunContext,
    cfg: ConfigRuntime,
    logger: PipelineLogger,
) -> tuple[list[NormalizedTable], tuple[Path, ...]]:
    ...
```

Phases:

1. `EXTRACTING` → `extract_tables`
2. `MAPPING` / `NORMALIZING` → per table
3. `WRITING_OUTPUT` → `write_workbook`
4. `COMPLETED` or `FAILED`

Each phase change is recorded via `logger.transition(phase, **payload)`.

---

## 7. Artifact and telemetry

### 7.1 Artifact (`artifact.py`)

The artifact is a JSON document that records:

* run metadata (ID, status, timestamps)
* config info (schema, version)
* tables (input metadata, mapping, validation issues)
* notes (high‑level narrative and hook‑written notes)

`FileArtifactSink` implements:

```python
class FileArtifactSink(ArtifactSink):
    def start(self, *, job: RunContext, manifest: dict): ...
    def note(self, message: str, *, level: str = "info", **extra): ...
    def record_table(self, table: dict): ...
    def mark_success(self, *, completed_at: datetime, outputs: Iterable[Path]): ...
    def mark_failure(self, *, completed_at: datetime, error: Exception): ...
    def flush(self): ...
```

The backing JSON shape is simple and self‑describing; structurally it might look like:

```jsonc
{
  "schema": "ade.artifact/v1",
  "artifact_version": "1.0.0",
  "run": {
    "run_id": "run-uuid",
    "status": "succeeded",
    "started_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:00:05Z",
    "outputs": [".../normalized.xlsx"],
    "metadata": {
      "job_id": "optional-job-id-from-backend",
      "config_id": "config-abc",
      "workspace_id": "ws-123"
    }
  },
  "config": {
    "schema": "ade.manifest/v1.0",
    "manifest_version": "1.2.3",
    "title": "My Config"
  },
  "tables": [
    {
      "input_file": "input.xlsx",
      "input_sheet": "Sheet1",
      "header": {
        "row_index": 5,
        "cells": ["ID","Email", "..."]
      },
      "mapping": [
        {
          "field": "member_id",
          "header": "ID",
          "source_column_index": 0,
          "score": 0.92,
          "contributions": [
            {"field": "member_id", "detector": "ade_config.column_detectors.member_id.detect_header_synonyms", "delta": 0.6},
            {"field": "member_id", "detector": "ade_config.column_detectors.member_id.detect_value_shape", "delta": 0.32}
          ]
        }
      ],
      "unmapped": [
        {
          "header": "Notes",
          "source_column_index": 5,
          "output_header": "raw_notes"
        }
      ],
      "validation": [
        {
          "row_index": 10,
          "field": "email",
          "code": "invalid_format",
          "severity": "error",
          "message": "Email must look like user@domain.tld"
        }
      ]
    }
  ],
  "notes": [
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "level": "info",
      "message": "Run started"
    }
  ]
}
```

Because every worker writes its own `artifact.json` for its run
(often in a per‑job logs folder chosen by the backend),
the ADE API can safely run many jobs in parallel without the engine
needing any shared global state.

### 7.2 Telemetry (`telemetry.py`)

Telemetry events are written as **newline‑delimited JSON** to `events.ndjson`.

Internally they are modeled as Pydantic classes in `ade_engine.schemas.telemetry`
(e.g. `TelemetryEnvelope`, `TelemetryEvent`). Those Python models can also emit a JSON Schema
for external consumers.

The envelope roughly looks like:

```jsonc
{
  "schema": "ade.telemetry/run-event.v1",
  "version": "1.0.0",
  "run_id": "run-uuid-or-correlation-id",
  "timestamp": "2024-01-01T12:34:56Z",
  "event": {
    "event": "run_started",
    "level": "info",
    "job_id": "optional-job-id-from-metadata",
    "config_id": "config-abc",
    "workspace_id": "ws-123"
  }
}
```

`PipelineLogger` is the only thing pipeline code touches:

```python
logger.note("Run started", level="info", extra="...")
logger.event("file_processed", level="info", file="input.xlsx", mapped_fields=[...])
logger.transition("extracting", file_count=3)
logger.record_table({...})   # artifact
```

The ADE API can:

* read `events.ndjson` to drive UIs / reporting, or
* plug in additional event sinks (e.g., send to a message bus) via `TelemetryConfig`.

---

## 8. Script API overview (config side)

For completeness, here’s the **contract** between the engine and `ade_config`.

All script entrypoints are **keyword‑only** functions and should accept `**_` to stay forward compatible.

Although the parameter is named `job` for historical reasons, it is really a `RunContext`
containing the manifest, paths, metadata, etc., and **does not require a job ID**.

### 8.1 Row detectors (`ade_config.row_detectors.header` / `data`)

```python
def detect_*(
    *,
    job,                 # RunContext (read-only from config’s perspective)
    state: dict,
    row_index: int,      # 1-based index in the sheet
    row_values: list,    # raw cell values for this row
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> dict:
    return {"scores": {"header": 0.7}}   # or {"scores": {"data": 0.4}}
```

### 8.2 Column detectors (`ade_config.column_detectors.<field>`)

```python
def detect_*(
    *,
    job,
    state: dict,
    field_name: str,
    field_meta: dict,            # manifest["columns"]["meta"][field_name]
    header: str | None,          # normalized header text
    column_values_sample: list,
    column_values: tuple,
    table: dict,                 # table summary (headers, row_count, etc.)
    column_index: int,           # 1-based
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> dict:
    return {"scores": {field_name: 0.8}}
```

### 8.3 Transforms

```python
def transform(
    *,
    job,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,                   # canonical row dict (field -> value)
    field_meta: dict | None,
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> dict | None:
    # Update row and/or return additional field mappings
    ...
```

### 8.4 Validators

```python
def validate(
    *,
    job,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_meta: dict | None,
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> list[dict]:
    # Return issue dicts: {"code": "invalid_format", "severity": "error", ...}
    ...
```

### 8.5 Hooks (`ade_config.hooks.*`)

```python
def run(
    *,
    job,               # RunContext
    state: dict,
    manifest: dict,
    env: dict | None,
    artifact,          # ArtifactSink
    events,            # EventSink | None
    tables=None,       # depends on stage: RawTable[] / MappedTable[] / NormalizedTable[]
    workbook=None,     # for on_before_save
    result=None,       # for on_run_end
    logger=None,
    **_,
) -> None:
    ...
```

Hook stages (manifest keys → `HookStage` mapping):

* `on_run_start` – before any IO or detection work
* `on_after_extract` – after `RawTable[]` has been built
* `on_after_mapping` – after `MappedTable[]` has been built (ideal for adjusting mappings)
* `on_before_save` – with the finalized `Workbook` and `NormalizedTable[]`
* `on_run_end` – after the run finishes (success or failure), with the `RunResult`

---

## 9. CLI usage

`cli.py` provides a small command‑line interface; `__main__.py` forwards to it.

Examples (all run inside the appropriate venv):

```bash
# Print engine version
python -m ade_engine --version

# Print engine version + manifest from a path (no run)
python -m ade_engine --manifest-path ./config/manifest.json

# Run the engine on a single file (typical worker call, paths chosen by backend)
python -m ade_engine \
  --input ./data/jobs/<job_id>/input/input.xlsx \
  --output-dir ./data/jobs/<job_id>/output \
  --logs-dir ./data/jobs/<job_id>/logs \
  --config-package ade_config \
  --manifest-path ./data/config_packages/my-config/manifest.json
```

The CLI prints a JSON summary including:

* engine version
* run ID
* status
* output paths
* artifact/events paths
* error (if any)

The ADE backend uses this pattern to run jobs asynchronously: the API enqueues a job;
a worker process/thread in the correct venv executes the CLI; the engine does its work
and writes outputs/logs; the API reads `artifact.json`/`events.ndjson` to drive UIs and reports.

---

## 10. Design principles

This architecture is intentionally:

* **Config‑centric** – ADE engine is a generic spreadsheet pipeline,
  driven entirely by `ade_config` (manifest + scripts).
* **Path‑based, not job‑based** – the engine deals in **files and folders** only.
  Job IDs and higher‑level orchestration live in the ADE API.
* **Predictable** – All public entry points and file names follow standard patterns:

  * `Engine.run`, `RunRequest`/`RunResult`
  * `execute_pipeline()`, `extract.py`, `mapping.py`, `normalize.py`, `write.py`
  * `io.py`, `config_runtime.py`, `hooks.py`, `artifact.py`, `telemetry.py`
* **Python‑first schemas** – Manifest and telemetry schemas are defined as Python models
  (Pydantic), with JSON Schemas generated as artifacts when needed.
* **Auditable** – Every detector score, transform, and validation issue can be
  explained via `artifact.json` and `events.ndjson`.
* **Isolated & composable** – Each config build gets its own venv; each engine call runs
  inside that venv, so changes to one config or environment never leak into others.
* **Extensible** – Hooks, telemetry sinks, and script API support evolving needs
  without changing the engine’s core.

With this README and the folder layout above, you should be able to reason about
the engine from scratch and confidently implement or refactor any part of it.
```

# apps/ade-engine/docs/01-engine-runtime.md
```markdown
# ADE Engine Runtime

This document describes what a **single ADE engine run** is, how it is invoked
(Programmatic + CLI), and how the core runtime types (`RunRequest`,
`RunContext`, `RunResult`) fit together.

It assumes:

- You are running inside a **pre-built virtual environment** that already has:
  - `ade_engine` installed.
  - Exactly one `ade_config` package installed (the config for this run).
- You’ve read the top-level `README.md` for the high-level architecture.

---

## 1. Purpose and boundaries

A single engine run is:

> A pure, path‑based function that takes **config + input files** and produces
> a **normalized workbook + artifact + telemetry**, with no knowledge of jobs.

From inside the venv, the engine:

- Accepts a **config** to use (`config_package`, optional `manifest_path`).
- Accepts **inputs** (`input_files` or `input_root`, optional `input_sheets`).
- Accepts where to put **outputs** (`output_root`, `logs_root`).
- Accepts opaque **metadata** from the caller (job IDs, etc., if desired).

It emits:

- One or more **normalized Excel workbooks** in `output_root`.
- An **artifact JSON** (`artifact.json`) in `logs_root`.
- **Telemetry events** (`events.ndjson`) in `logs_root`.
- A **`RunResult`** describing the outcome.

The engine **does not**:

- Know about job queues, tenants, workspaces, or job IDs.
- Own virtual environment creation, scaling, or scheduling.
- Enforce OS‑level limits (CPU, memory, time). That’s the backend’s job.

---

## 2. Entry points

### 2.1 Programmatic API (`Engine` and `run()`)

Most code uses the high‑level API exposed by `ade_engine.__init__`:

```python
from pathlib import Path
from ade_engine import Engine, run, RunRequest

# Full control via RunRequest
engine = Engine()
result = engine.run(
    RunRequest(
        config_package="ade_config",
        input_files=[Path("input.xlsx")],
        output_root=Path("output"),
        logs_root=Path("logs"),
        metadata={"job_id": "123"},
    )
)

# Convenience helper (sugar over Engine.run)
result = run(
    input_files=[Path("input.xlsx")],
    output_root=Path("output"),
    logs_root=Path("logs"),
)
````

Characteristics:

* `Engine` is **logically stateless**:

  * No per‑run state is kept on the instance.
  * You can safely reuse a single `Engine` across threads as long as each
    call uses its own `RunRequest`.
* The top‑level `run(...)` helper:

  * Builds a `RunRequest` from keyword arguments.
  * Creates a short‑lived `Engine`.
  * Returns a `RunResult`.

### 2.2 CLI (`python -m ade_engine`)

The CLI is a thin layer over the same runtime:

```bash
python -m ade_engine \
  --input ./input.xlsx \
  --output-dir ./output \
  --logs-dir ./logs \
  --config-package ade_config
```

The CLI:

* Parses flags into a `RunRequest`-like structure.
* Runs the engine once.
* Prints a **JSON summary** (with status, paths, error) to stdout.
* Sets a **non‑zero exit code** on failure.

Details of flags and JSON shape are documented in `09-cli-and-integration.md`.
The runtime behavior is the same as the programmatic API.

---

## 3. Core runtime types

Most runtime complexity is expressed via a few core types in `types.py`.

### 3.1 `RunRequest` – “what to run”

`RunRequest` describes the configuration of a single engine run:

* **Config**

  * `config_package: str`
    Python package name to import. Defaults to `"ade_config"`.
  * `manifest_path: Path | None`
    Optional path overriding `ade_config/manifest.json`.

* **Inputs** (mutually exclusive; one must be provided)

  * `input_files: Sequence[Path] | None`
    Explicit list of files (preferred; typical shape: `[Path("input.xlsx")]`).
  * `input_root: Path | None`
    Directory to discover files in (e.g., `input/` folder).

* **Sheet filter**

  * `input_sheets: Sequence[str] | None`
    Restrict XLSX processing to specific sheet names. CSV has a single implicit
    sheet; this filter has no effect on CSV.

* **Outputs**

  * `output_root: Path | None`
    Directory for normalized workbook(s).
  * `logs_root: Path | None`
    Directory for `artifact.json` and `events.ndjson`.

* **Options**

  * `safe_mode: bool`
    Hint for more conservative execution (e.g., reduced integrations). Exact
    semantics are handled by the engine and/or config.
  * `metadata: Mapping[str, Any] | None`
    Opaque caller metadata (e.g., `{"job_id": "...", "config_id": "..."}`).

Invariants:

* Exactly one of `input_files` or `input_root` **must** be set.
* If both are set, the engine fails fast with a clear error.
* All paths are normalized to absolute paths near the start of `Engine.run`.

### 3.2 `RunPaths` – resolved filesystem layout

`RunPaths` represents a **normalized, concrete directory layout**:

* `input_root: Path`
* `output_root: Path`
* `logs_root: Path`
* `artifact_path: Path`   (within `logs_root`)
* `events_path: Path`     (within `logs_root`)

Resolution rules (conceptual):

1. **Input root**

   * If `RunRequest.input_root` is provided, use it.
   * Else, use the parent of the first `RunRequest.input_files` entry.

2. **Output / logs roots**

   * If provided explicitly in `RunRequest`, use them as‑is.
   * Otherwise, infer sensible defaults relative to `input_root`
     (e.g., sibling `output/` and `logs/` directories).

3. **File names**

   * `artifact_path` is `logs_root / "artifact.json"`.
   * `events_path` is `logs_root / "events.ndjson"`.
   * Normalized workbook filename(s) are chosen by the writer (usually a
     manifest‑driven name, often a single workbook under `output_root`).

These decisions are made once, up front, and never mutated mid‑run.

### 3.3 `RunContext` – per-run state

`RunContext` is what config code “sees” as the `job` argument. It contains:

* `run_id: str`
  Unique identifier per run (e.g. UUID).

* `paths: RunPaths`
  Fully resolved filesystem layout.

* `manifest: ManifestContext`
  Wrapper around the loaded manifest (Pydantic model + convenience helpers).

* `env: dict[str, str]`
  From `manifest.env`. This is the config‑level environment, not OS env vars.

* `metadata: dict[str, Any]`
  Copy of `RunRequest.metadata`. The engine treats this as an opaque dict.

* `safe_mode: bool`
  Copied from `RunRequest.safe_mode`.

* `started_at: datetime` / `completed_at: datetime | None`
  Timestamps for run lifecycle.

* `state: dict[str, Any]`
  Per‑run mutable scratch space, shared across detectors, transforms,
  validators, and hooks.

Properties:

* A new `RunContext` is created for every call to `Engine.run`.
* No `RunContext` is shared across runs.
* Config authors can use `state` for caches, counters, etc., within a single
  run; never for cross‑run state.

### 3.4 `RunResult` – outcome summary

`RunResult` is what `Engine.run` (and the top‑level `run()`) returns:

* `status: Literal["succeeded", "failed"]`
* `error: str | None`
  Short, human‑readable summary for failures; `None` for success.
* `output_paths: tuple[Path, ...]`
  One or more normalized workbook paths (often a single workbook).
* `artifact_path: Path`
  Path to `artifact.json`.
* `events_path: Path`
  Path to `events.ndjson`.
* `processed_files: tuple[str, ...]`
  Basenames of all input files that were actually processed.

Guarantees:

* On **success**:

  * `status == "succeeded"`.
  * `output_paths` is non‑empty and each path exists.
* On **both** success and failure:

  * `artifact_path` and `events_path` exist.
  * `artifact.json` is complete and parseable.

### 3.5 Pipeline phases

Internally, the engine tracks a `PipelinePhase` enum, roughly:

* `INITIALIZED`
* `EXTRACTING`
* `MAPPING`
* `NORMALIZING`
* `WRITING_OUTPUT`
* `COMPLETED`
* `FAILED`

Phase transitions are recorded in telemetry and may be reflected in
`artifact.notes`. They are mostly relevant to observability and debugging.

---

## 4. Run lifecycle

The lifecycle below describes what happens inside `Engine.run(request)`.

### 4.1 Preparation

1. **Normalize `RunRequest`**

   * Validate invariants (`input_files` vs `input_root`).
   * Resolve paths and build `RunPaths`.

2. **Create `RunContext`**

   * Generate `run_id`.
   * Initialize `started_at`.
   * Initialize empty `state` dict.
   * Attach `RunPaths`, `metadata`, `safe_mode`.

3. **Load manifest and config runtime**

   * Import `config_package` (default `ade_config`).
   * Locate and load `manifest.json` or use `manifest_path` override.
   * Validate manifest into `ManifestV1` (Pydantic).
   * Build `ManifestContext`.
   * Discover and register:

     * row detectors,
     * column detectors,
     * transforms,
     * validators,
     * hooks.

4. **Initialize telemetry and artifact**

   * Bind telemetry sinks based on `TelemetryConfig` (if provided) and
     `RunContext.metadata`.
   * Create `ArtifactSink` (file‑backed writer to `artifact.json`).
   * Construct a `PipelineLogger` that wraps artifact + telemetry sinks.

### 4.2 Start events and hooks

5. **Mark run as started**

   * Write an initial artifact structure:

     * run ID, started_at, initial status (`"running"`), config metadata.
   * Emit a `run_started` telemetry event (with metadata).

6. **Run `on_run_start` hooks**

   * Call any hooks registered for `on_run_start` with:

     * `job` (`RunContext`),
     * `state`,
     * `manifest`,
     * `env`,
     * `artifact`,
     * `events`,
     * `logger`.
   * Typical hook tasks:

     * Initialize caches,
     * Log environment/config summary,
     * Perform quick preflight checks.

If any of these steps fail, the error is handled as described in
[Section 5](#5-error-handling).

### 4.3 Pipeline execution

7. **Extract**

   * Phase: `EXTRACTING`.
   * Discover input files (if using `input_root`) and read CSV/XLSX sheets.
   * Run row detectors to identify headers and data ranges.
   * Build `RawTable[]` and record them in the artifact as needed.
   * Call any `on_after_extract` hooks.

8. **Map**

   * Phase: `MAPPING`.
   * For each `RawTable`:

     * Run column detectors and scoring.
     * Produce `MappedTable` with `ColumnMapping[]` and `ExtraColumn[]`.
   * After all tables are mapped:

     * Call `on_after_mapping` hooks (pass the mapped tables).

9. **Normalize**

   * Phase: `NORMALIZING`.
   * For each `MappedTable`:

     * Build canonical rows.
     * Apply transforms and validators per field.
     * Aggregate `ValidationIssue[]`.
     * Produce `NormalizedTable[]`.

10. **Write output**

    * Phase: `WRITING_OUTPUT`.
    * Use writer config from manifest to:

      * Decide whether to output a single combined workbook vs multiple sheets
        / workbooks.
      * Build header rows (canonical fields + extras).
      * Append normalized rows in a deterministic order.
    * Call `on_before_save` hooks with:

      * `NormalizedTable[]`,
      * a live workbook object (e.g., openpyxl `Workbook`).
    * Save workbook(s) into `output_root`.
    * Return a list of `Path` objects (output workbooks).

### 4.4 Finalization

11. **Mark success in artifact and telemetry**

    * Update artifact run section:

      * `status = "succeeded"`,
      * `completed_at`,
      * `outputs` = list of workbook paths.
    * Emit `run_completed` telemetry event.
    * Flush artifact and telemetry sinks.

12. **Run `on_run_end` hooks**

    * Hooks see:

      * `job` (`RunContext`),
      * `state`,
      * `manifest`, `env`,
      * `artifact`, `events`,
      * `result` (a provisional `RunResult`),
      * `logger`.
    * Hooks can:

      * Emit final notes and metrics,
      * Perform clean‑up or side‑effect integrations.

13. **Return `RunResult`**

    * With `status="succeeded"`,
    * `output_paths` as produced by the writer,
    * `artifact_path` and `events_path` from `RunPaths`,
    * `processed_files` set to the input basenames that were actually read.

---

## 5. Error handling

Any unhandled exception during a run is translated into a **failed run** with a
useful artifact and telemetry record.

### 5.1 Error categories

Conceptually:

* **Config errors**

  * Invalid manifest JSON.
  * Missing or misconfigured column scripts / hooks.
  * Signature mismatches in detectors/transforms/validators.

* **Input errors**

  * Input file does not exist or cannot be read.
  * Required sheet missing.
  * No usable tables discovered.

* **Engine errors**

  * Bugs or unexpected exceptions inside `ade_engine` itself.

The runtime generally does not distinguish these categories in types, but they
inform how error messages are written.

### 5.2 Behavior on failure

On any unhandled exception:

1. Pipeline phase is set to `FAILED`.
2. Artifact is updated:

   * `run.status = "failed"`,
   * `completed_at = now`,
   * `error` information recorded (type/message, optionally a code).
3. A `run_failed` telemetry event is emitted with context.
4. Sinks are flushed (artifact + telemetry).
5. `RunResult` is returned with:

   * `status="failed"`,
   * `error` set to a human‑readable summary,
   * `output_paths` possibly empty or partial,
   * `artifact_path` and `events_path` pointing to complete log files.

The **goal** is that a failed run is still debuggable by looking at
`artifact.json` and `events.ndjson`.

---

## 6. Interaction with virtual environments and ADE backend

The runtime is intentionally simple and **job‑agnostic**. The typical backend
integration looks like this:

1. ADE backend decides which config version to use.

2. Backend ensures a venv exists with:

   * `ade_engine`,
   * that specific `ade_config` version.

3. Backend prepares a per‑job directory structure, e.g.:

   ```text
   /data/jobs/<job_id>/
     input/
       input.xlsx
     output/
     logs/
   ```

4. A worker activates the venv and calls either:

   **Python API:**

   ```python
   from pathlib import Path
   from ade_engine import run

   result = run(
       config_package="ade_config",
       input_files=[Path(f"/data/jobs/{job_id}/input/input.xlsx")],
       output_root=Path(f"/data/jobs/{job_id}/output"),
       logs_root=Path(f"/data/jobs/{job_id}/logs"),
       metadata={"job_id": job_id, "config_id": config_id},
   )
   ```

   **or CLI:**

   ```bash
   python -m ade_engine \
     --input "/data/jobs/${job_id}/input/input.xlsx" \
     --output-dir "/data/jobs/${job_id}/output" \
     --logs-dir "/data/jobs/${job_id}/logs" \
     --config-package ade_config
   ```

5. Backend:

   * Stores references to `result.output_paths`, `artifact.json`, and
     `events.ndjson` in its own job record.
   * Uses `artifact.json` and `events.ndjson` for reporting and UI.

The engine never needs to know what `job_id` means; it just sees file paths and
optional metadata.

---

## 7. Concurrency and state

The runtime is designed to be safe under typical worker pool patterns.

* **Engine instances**

  * `Engine` holds configuration (e.g., `TelemetryConfig`), not run state.
  * It is safe to:

    * Instantiate a new `Engine` per run, or
    * Share a single `Engine` across threads/tasks, as long as each `run()`
      call uses a distinct `RunRequest`.

* **RunContext**

  * Every call to `Engine.run` creates a fresh `RunContext` with its own `state`
    dict.
  * Nothing inside `RunContext` is shared across runs.

* **Global state**

  * The engine avoids mutable module‑level globals wherever possible.
  * Config code should use `RunContext.state` or external systems (databases,
    caches) rather than global variables.

Backend concurrency (threads vs processes vs containers) is outside the scope of
the runtime; the engine just expects a functioning Python process with the
correct venv activated.

---

With these pieces in mind, you can treat the runtime as a predictable black box:
**provide a config and inputs, get normalized outputs and detailed logs**, with
clear points to plug in config‑specific behavior via scripts and hooks.
```

# apps/ade-engine/docs/02-config-and-manifest.md
```markdown
# Config Runtime & Manifest

This document describes how the **ADE engine** discovers and uses a config
package (`ade_config`) and its `manifest.json`, and how that manifest is
represented as Python models inside `ade_engine`.

Read this if you are:

- implementing `config_runtime.py`,
- authoring or reviewing a config package,
- or wiring config‑driven behavior into new parts of the engine.

---

## 1. What a config package is

At runtime, the engine expects **one Python package** that defines all
business‑specific behavior:

- which columns exist and in what order,
- how to detect tables and fields,
- how to normalize and validate values,
- which hooks to run at various stages, and
- writer / environment defaults.

By default this package is named **`ade_config`** and is installed into the same
virtual environment as `ade_engine`.

Conceptually:

```text
ade_config/                     # business logic (per customer / per config)
  __init__.py
  manifest.json                 # required manifest file
  row_detectors/                # optional: header/data row detectors
    __init__.py
    header.py
    data.py
  column_detectors/             # detectors + transform + validate per field
    __init__.py
    member_id.py
    email.py
    ...
  hooks/                        # lifecycle hooks
    __init__.py
    on_run_start.py
    on_after_extract.py
    on_after_mapping.py
    on_before_save.py
    on_run_end.py
  _shared.py                    # optional helper code shared across scripts
````

The **engine is generic**. Everything domain‑specific lives in this package and
is defined by the manifest.

---

## 2. The manifest: single source of truth

### 2.1 Location and format

The manifest is a JSON file shipped with the config package:

* Default path: `<config_package>/manifest.json`.
* Optional override: a `--manifest-path` CLI flag or `RunRequest.manifest_path`
  can point to a different file.
* Encoding: UTF‑8 JSON.

Although it is stored as JSON, the **schema is defined in Python** in
`ade_engine.schemas.manifest` (see section 3). The JSON is just data; the
Python models are authoritative.

### 2.2 High‑level structure

The manifest has a small number of top‑level sections:

```jsonc
{
  "config_script_api_version": "1",
  "info": {
    "schema": "ade.manifest/v1.0",
    "title": "My Config",
    "version": "1.2.3",
    "description": "Optional description"
  },
  "env": {
    "LOCALE": "en-CA",
    "DATE_FMT": "%Y-%m-%d"
  },
  "engine": {
    "defaults": {
      "timeout_ms": 180000,
      "memory_mb": 384,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.35,
      "detector_sample_size": 64
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_",
      "output_sheet": "Normalized"
    }
  },
  "hooks": {
    "on_run_start":     [{ "script": "hooks/on_run_start.py" }],
    "on_after_extract": [{ "script": "hooks/on_after_extract.py" }],
    "on_after_mapping": [{ "script": "hooks/on_after_mapping.py" }],
    "on_before_save":   [{ "script": "hooks/on_before_save.py" }],
    "on_run_end":       [{ "script": "hooks/on_run_end.py" }]
  },
  "columns": {
    "order": ["member_id", "email", "..."],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "script": "column_detectors/member_id.py",
        "required": true,
        "enabled": true,
        "synonyms": ["member id", "member#"],
        "type_hint": "string"
      },
      "email": {
        "label": "Email",
        "script": "column_detectors/email.py",
        "required": true,
        "enabled": true,
        "type_hint": "string"
      }
    }
  }
}
```

Key ideas:

* **`info`** describes the config itself and how to interpret the manifest.
* **`env`** is a small string‑keyed map passed into all scripts.
* **`engine`** controls engine‑side behavior (defaults, writer behavior).
* **`hooks`** defines lifecycle customizations.
* **`columns`** declares what canonical fields exist and how to handle them.

---

## 3. Python schema and `ManifestContext`

### 3.1 `ManifestV1` (Pydantic model)

In `ade_engine/schemas/manifest.py` the manifest is modeled as a Pydantic
class, e.g.:

* `ManifestV1`

  * `config_script_api_version: str`
  * `info: ManifestInfo`
  * `env: dict[str, str]`
  * `engine: EngineConfig` (with `defaults` and `writer`)
  * `hooks: HookCollection`
  * `columns: ColumnSection`

Engine code **never** hard‑codes raw JSON keys; it works with these models.

From the models, the engine can optionally emit JSON Schema
(`ManifestV1.model_json_schema()`) for validation in other systems.

### 3.2 `ManifestContext` helper

At runtime the manifest is wrapped in a lightweight helper:

```python
class ManifestContext:
    raw: dict                 # original JSON dict
    model: ManifestV1         # validated Pydantic model

    @property
    def column_order(self) -> list[str]: ...
    @property
    def column_meta(self) -> dict[str, ColumnMeta]: ...
    @property
    def defaults(self) -> EngineDefaults: ...
    @property
    def writer(self) -> EngineWriter: ...
    @property
    def env(self) -> dict[str, str]: ...
```

This gives the pipeline and config runtime a clean, typed surface:

* `ctx.manifest.column_order` to drive output ordering,
* `ctx.manifest.column_meta["email"]` to look up script paths and flags,
* `ctx.manifest.defaults.mapping_score_threshold` for mapping,
* `ctx.manifest.writer.append_unmapped_columns` for output behavior,
* `ctx.manifest.env` for script configuration.

The **same `ManifestContext` instance** is stored on `RunContext` and passed to
scripts via the `job` argument (see script API docs).

---

## 4. Loading config at runtime (`config_runtime`)

### 4.1 Responsibilities of `config_runtime`

The `config_runtime` module is the “glue” between:

* the `ade_config` package and its `manifest.json`, and
* the rest of the engine.

It is responsible for:

1. **Finding and parsing the manifest** into a `ManifestContext`.
2. **Resolving scripts** (row detectors, column modules, hooks).
3. **Building registries** that the pipeline can use:

   * `ConfigRuntime.columns` (column registry),
   * `ConfigRuntime.hooks` (hook registry),
   * plus convenient access to `env`, defaults, writer, etc.

A typical public entrypoint looks like:

```python
def load_config_runtime(
    package: str = "ade_config",
    manifest_path: Path | None = None,
) -> ConfigRuntime:
    ...
```

### 4.2 Manifest resolution rules

The manifest is resolved with a simple algorithm:

1. Import the config package:

   ```python
   pkg = importlib.import_module(package)
   ```

2. Determine manifest path:

   * If `manifest_path` is provided:

     * Use that file.
   * Else:

     * Use `importlib.resources.files(pkg) / "manifest.json"`.

3. Read and parse JSON.

4. Validate via `ManifestV1.model_validate(raw)`.

5. Wrap as `ManifestContext`.

Any structural error in `manifest.json` should fail fast here, **before** any
pipeline work starts.

---

## 5. Column metadata and column registry

### 5.1 `columns.order`

`columns.order` defines the **canonical field order** in the normalized
workbook:

* It is a list of canonical field IDs (keys of `columns.meta`).
* It controls:

  * the logical column order in the normalized sheet,
  * tie‑breaking in column mapping (earlier fields win on equal scores),
  * the order in which transforms/validators see fields (if applicable).

If some fields in `columns.meta` are **not** included in `columns.order`, they
are considered defined but not part of the main output ordering. The engine may
still use them if scripts reference them explicitly.

### 5.2 `columns.meta` and `ColumnMeta`

For each canonical field, `columns.meta[field_name]` describes how to handle it.
Typical keys:

* `label: str`
  Human‑friendly column label for the normalized workbook.
* `script: str`
  Path to the column script inside the config package, e.g.
  `"column_detectors/email.py"`.
* `required: bool`
  Whether the field is semantically required (used by validators and reporting).
* `enabled: bool`
  If `false`, the field is ignored by mapping and normalization.
* `synonyms: list[str]`
  Common alternate header names; often used by detectors.
* `type_hint: str`
  Optional scalar type hint (e.g. `"string"`, `"date"`, `"integer"`).

The `ColumnMeta` Pydantic model captures this shape and enforces basic typing.

### 5.3 From `ColumnMeta` to `ColumnModule`

At runtime, `config_runtime` builds a **column registry** from the manifest:

1. For each `field_name` in `columns.meta`:

   * Resolve `script` to a module name:

     ```text
     "column_detectors/email.py"
       → "ade_config.column_detectors.email"
     ```

   * Import the module.

2. For each module:

   * Collect all `detect_*` callables (column detectors).
   * Optionally record:

     * `transform` function.
     * `validate` function.

3. Wrap this into a `ColumnModule` object, e.g.:

   ```python
   @dataclass
   class ColumnModule:
       field: str
       definition: ColumnMeta
       module: ModuleType
       detectors: list[Callable]
       transformer: Callable | None
       validator: Callable | None
   ```

4. Store in a `ColumnRegistry` keyed by `field` name.

Mapping and normalization code later uses this registry rather than inspecting
modules directly.

### 5.4 Signature validation

When building the registry, `config_runtime` validates that:

* Detectors, transformers, and validators are callable.
* Functions support the expected keyword‑only API (and `**_` for forward
  compatibility).

If a function is missing or has an incompatible signature, the engine treats
this as a **config error** and fails loading before processing any input.

---

## 6. Hooks in the manifest and hook registry

### 6.1 Manifest `hooks` section

The `hooks` section describes which scripts to run at each lifecycle stage:

```jsonc
"hooks": {
  "on_run_start": [
    { "script": "hooks/on_run_start.py", "enabled": true }
  ],
  "on_after_extract": [
    { "script": "hooks/on_after_extract.py" }
  ],
  "on_after_mapping": [
    { "script": "hooks/on_after_mapping.py" }
  ],
  "on_before_save": [
    { "script": "hooks/on_before_save.py" }
  ],
  "on_run_end": [
    { "script": "hooks/on_run_end.py" }
  ]
}
```

Each hook entry is a small object with:

* `script: str` — path inside the config package, e.g. `"hooks/on_run_end.py"`.
* Optional `enabled: bool` — defaults to `true` if omitted.

### 6.2 Building the hook registry

`config_runtime` turns the manifest `hooks` section into a `HookRegistry`:

1. For each stage (e.g. `on_run_start`):

   * For each hook entry:

     * Resolve `script` path to a module name:

       ```text
       "hooks/on_run_start.py"
         → "ade_config.hooks.on_run_start"
       ```

     * Import the module.

     * Select an entrypoint:

       * Prefer a `run` function.
       * Fallback to `main` if `run` is absent.
2. Store the callables in order for each stage.

The engine later invokes hooks by stage name, using a standard keyword‑only
signature. Any import or runtime error is surfaced as a clear hook error and
fails the run.

---

## 7. Config `env` and how scripts see it

### 7.1 Manifest `env` section

`env` is a simple key–value map:

```jsonc
"env": {
  "LOCALE": "en-CA",
  "DATE_FMT": "%Y-%m-%d",
  "MAX_ROWS": "500000"
}
```

Characteristics:

* All keys and values are strings in the manifest.
* It is meant for **config‑level settings**, *not* arbitrary environment
  variables from the OS.

### 7.2 Exposure in runtime and scripts

`env` travels through the system as:

* `RunContext.env` (dict of `str → str`).
* A `env` parameter to:

  * row detectors,
  * column detectors,
  * transforms,
  * validators,
  * hooks.

Scripts can then do:

```python
date_fmt = env.get("DATE_FMT", "%Y-%m-%d")
```

Rather than reading `os.environ` directly. This keeps behavior deterministic for
a given manifest and makes configs easier to reason about.

---

## 8. Config runtime aggregate: `ConfigRuntime`

Putting everything together, `config_runtime` exposes a small aggregate object
used by the pipeline:

```python
@dataclass
class ConfigRuntime:
    manifest: ManifestContext
    columns: ColumnRegistry
    hooks: HookRegistry
    # Optional additional views:
    #   defaults, writer, env, etc., as convenience properties.
```

The engine typically does:

```python
cfg = load_config_runtime(package=request.config_package,
                          manifest_path=request.manifest_path)

ctx.manifest = cfg.manifest
# pass `cfg` into pipeline stages for access to column registry and hooks
```

From this point on, **all config behavior** is driven by:

* the manifest model (`cfg.manifest`),
* the column registry (`cfg.columns`),
* the hook registry (`cfg.hooks`),
* and the shared `env` exposed via `RunContext`.

---

## 9. Versioning and compatibility

Two fields in the manifest control how configs evolve over time:

* `info.schema` (e.g. `"ade.manifest/v1.0"`):

  * Identifies the manifest schema version.
  * Used by the engine and tooling to decide which Pydantic model to use.
* `config_script_api_version` (e.g. `"1"`):

  * Indicates which **script API contract** the config expects
    (parameters of detectors, transforms, validators, hooks).

Guidelines:

* Adding new optional manifest fields or `env` keys is safe and should be
  backwards compatible.
* Changing or removing manifest fields, or changing script signatures, should:

  * bump either `info.schema` or `config_script_api_version`, and
  * be treated as a breaking change for existing configs.

The ADE backend is responsible for:

* tying a particular **config version** (`info.version`) to a specific venv
  build, and
* ensuring that config and engine versions that share a venv agree on
  `info.schema` and `config_script_api_version`.

With these rules, you can evolve both the engine and config packages without
mysterious runtime breakage.
```

# apps/ade-engine/docs/03-io-and-table-detection.md
```markdown
# IO and Table Detection

This document describes how the ADE engine:

1. Discovers **input files** (CSV/XLSX),
2. Streams **rows** from those files in a memory‑friendly way, and
3. Uses **row detectors** from `ade_config` to turn raw sheets into `RawTable`
   objects that feed the mapping stage.

It assumes you’ve read:

- `README.md` (high‑level architecture)
- `01-engine-runtime.md`
- `02-config-and-manifest.md`

Relevant modules:

- `io.py` — low‑level file and sheet IO.
- `pipeline/extract.py` — table detection over streamed rows.
- `ade_config.row_detectors` — config‑side detection scripts.

---

## 1. Responsibilities and constraints

The IO + extract layer has three core responsibilities:

1. **Turn a `RunRequest` into a deterministic sequence of input files.**
2. **Stream rows** from CSV/XLSX without loading whole workbooks into memory.
3. **Locate tables** in each sheet by running row detectors and emitting
   `RawTable` objects.

Design constraints:

- **No job/backend knowledge** — everything is path‑based.
- **Streaming‑friendly** — large workbooks should not require large amounts
  of memory.
- **Config‑driven** — row detectors are provided by `ade_config`, not hard‑coded.
- **Predictable ordering** — given the same inputs and config, detection is
  deterministic.

The output of this layer is a list of `RawTable` objects that fully describe
each detected table, including header row, data rows, and location metadata.

---

## 2. From RunRequest to input files

### 2.1 Sources: `input_files` vs `input_root`

`RunRequest` offers two ways to specify inputs:

- `input_files: Sequence[Path]`  
  Explicit list of files to process.

- `input_root: Path`  
  A directory to scan for input files.

Invariants enforced upstream (in `Engine.run`):

- Exactly **one** of `input_files` or `input_root` must be set.
- Paths are normalized to absolute paths before use.

### 2.2 File discovery

When `input_root` is provided, `io.list_input_files` is used to discover files:

```python
def list_input_files(input_root: Path) -> list[Path]:
    """
    Return a sorted list of CSV/XLSX files under input_root.

    - Ignores hidden files and directories (implementation detail).
    - Filters by extension (.csv, .xlsx).
    - Returns absolute Paths in a deterministic order.
    """
````

Characteristics:

* **Deterministic order** — ensures reproducible results and artifact output.
* **Simple filter** — engine currently supports `.csv` and `.xlsx` only.
* Discovery is **shallow vs recursive** based on implementation; whatever we
  choose should be documented and stable.

When `input_files` is provided, `list_input_files` is skipped; the engine uses
the given list as‑is (after normalization).

### 2.3 File type classification

Each discovered input is classified by extension:

* `.csv` → **CSV file**
* `.xlsx` → **XLSX workbook**

Unsupported extensions are rejected early with a clear, user‑facing error
(e.g., “File `foo.xls` has unsupported extension `.xls`”).

---

## 3. CSV IO

### 3.1 Streaming rows from CSV

CSV files are treated as a single logical sheet.

`io.py` provides a helper similar to:

```python
def iter_csv_rows(path: Path) -> Iterable[tuple[int, list]]:
    """
    Stream (row_index, row_values) from a CSV file.

    - row_index is 1-based.
    - row_values is a list of Python primitives (usually strings).
    - Uses UTF-8 with BOM tolerance by default.
    """
```

Behavior:

* Uses `csv.reader` (or equivalent) to iterate rows.
* Keeps only one row in memory at a time.
* Passes raw values straight into row detectors; further normalization can
  happen in detectors or later stages if needed.

### 3.2 CSV and tables

By default, the engine assumes:

* **One potential table per CSV file.**

Row detectors still decide where the header and data blocks are, but the engine
does not try to find multiple independent tables in a single CSV. That is a
possible future extension.

---

## 4. XLSX IO

### 4.1 Workbook loading

XLSX files are opened in streaming mode using `openpyxl`:

```python
from openpyxl import load_workbook

def open_workbook(path: Path):
    return load_workbook(
        filename=path,
        read_only=True,
        data_only=True,
    )
```

Design goals:

* Never load entire workbook into memory when not necessary.
* Always work in terms of standard Python primitives:
  strings, numbers, booleans, `None`.

### 4.2 Sheet selection

The mapping from a workbook to sheets is:

* If `RunRequest.input_sheets` is **not** provided:

  * Process all visible sheets in workbook order.
* If `input_sheets` **is** provided:

  * Restrict to the named sheets.
  * Missing sheet names are treated as a **hard error** (“Worksheet `Foo`
    not found in `input.xlsx`”).

This mapping is applied per workbook, so different workbooks can have different
sheet sets.

### 4.3 Streaming rows from sheets

`io.py` provides a helper like:

```python
def iter_sheet_rows(path: Path, sheet_name: str) -> Iterable[tuple[int, list]]:
    """
    Stream (row_index, row_values) from a sheet in an XLSX file.

    - row_index is 1-based.
    - row_values is a list of simple Python values (str, float, bool, None, ...).
    """
```

Typical logic:

* Use `worksheet.iter_rows(values_only=True)` under the hood.
* Normalize values:

  * Excel blanks → `None`.
  * Formulas → evaluated values via `data_only=True` (not formulas).

The exact normalization strategy (e.g., whether to keep `None` or coerce to
`""`) should be stable and documented; any changes must be coordinated with
detectors and config authors.

---

## 5. Row detectors and table detection

### 5.1 Role of row detectors

Row detectors live in `ade_config.row_detectors` and are responsible for
identifying:

* **header rows** — where column names live,
* **data rows** — the main body of the table.

The engine **does not** hard‑code any notion of a header row or data start/end;
it relies entirely on detector scores and a small set of heuristics.

### 5.2 Detector API (config side)

A typical row detector has this shape:

```python
def detect_header_or_data(
    *,
    job,                 # RunContext (named "job" for historical reasons)
    state: dict,
    row_index: int,      # 1-based index within the sheet
    row_values: list,    # raw cell values for this row
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> dict:
    """
    Return a dict with per-label scores.

    Example:
        {"scores": {"header": 0.7, "data": 0.1}}
    """
```

Conventions:

* `job` is read‑only from the config’s perspective (it is a `RunContext`).
* `state` is a per‑run dict that detectors may use to coordinate across rows.
* `manifest` and `env` provide config‑level context (locale, date formats, etc.).
* `logger` allows emitting notes and telemetry if needed.
* Functions must accept `**_` to remain forwards‑compatible.

Return contract:

* A dict containing a `"scores"` key:

  * `"scores"` is a map from labels to floats.
  * Typical labels are `"header"` and `"data"`, but detectors may emit more
    specialized labels as long as the engine knows how to interpret them.

### 5.3 Aggregation and scoring

For each row of each sheet:

1. Engine calls all row detectors with that row.
2. Each detector returns a `"scores"` map.
3. Engine aggregates scores by label (e.g., `"header"`, `"data"`) by
   **summing contributions**.

The result is a per‑row summary like:

```python
RowScore = {
    "row_index": 12,
    "header_score": 0.85,
    "data_score": 0.15,
}
```

Exact thresholds and label names are implementation details but should be
documented in code comments and tests.

### 5.4 Heuristics for deciding table boundaries

Using row scores, `pipeline/extract.py` decides where tables begin and end.

Baseline behavior (for a single table per sheet):

1. Scan rows top‑down until a row passes a **header threshold**:

   * First such row → header row.
2. Starting from the row after the header:

   * Rows that pass a **data threshold** are considered data rows.
   * Trailing blocks of rows with very low data signal are ignored.
3. If no header or data block is found:

   * The sheet does not produce a `RawTable`.
   * Engine logs an informative diagnostic.

For CSV, the same logic is applied, but there is only a single “sheet.”

Heuristics (thresholds, minimum row counts, gap handling) are tunable in code
and may be influenced by manifest defaults (e.g., minimum data rows).

---

## 6. RawTable model

Once a table is identified, the engine materializes a `RawTable` dataclass
(see `types.py`), conceptually:

```python
@dataclass
class RawTable:
    source_file: Path
    source_sheet: str | None
    header_row: list[str]          # normalized header cells
    data_rows: list[list[Any]]     # all data rows for the table
    header_index: int              # 1-based row index of header in the sheet
    first_data_index: int          # 1-based row index of first data row
    last_data_index: int           # 1-based row index of last data row
```

Details:

* `source_file` — absolute path to the input file.
* `source_sheet` — sheet name for XLSX; `None` for CSV.
* `header_row` — header cells normalized to strings (e.g. `None` → `""`).
* `data_rows` — full set of rows between `first_data_index` and
  `last_data_index` that the algorithm considers part of the table.
* Indices are **1‑based** and correspond to original sheet row numbers; this
  is important for traceability and artifact reporting.

`RawTable` is the only table‑level type passed into column mapping.

---

## 7. Integration with artifact and telemetry

### 7.1 Artifact entries

During extraction, the engine records basic information in the artifact
(via `ArtifactSink`), such as:

* For each table:

  * `input_file`
  * `input_sheet`
  * `header.row_index`
  * `header.cells`
  * row counts, etc.

This allows later inspection of what the engine believed the table shape was,
even before mapping/normalization.

### 7.2 Telemetry events

`PipelineLogger` is available during extraction and may emit events like:

* `pipeline_transition` with phase `"EXTRACTING"`.
* `file_discovered` and `file_processed` for each file.
* `table_detected` for each `RawTable` built.

These events are written to `events.ndjson` and can be consumed by the ADE
backend for realtime progress indicators or metrics.

---

## 8. Edge cases and error handling

### 8.1 Empty files / sheets

* If a file or sheet yields no rows at all:

  * Engine records a note and skip it.
  * No `RawTable` is created.
* If detectors cannot identify a header/data region:

  * Engine may:

    * Treat it as “no tables found on sheet,” and/or
    * Emit a warning in artifact/telemetry.

Policies should be consistent and covered by tests.

### 8.2 Missing or invalid sheets

* If a sheet name listed in `input_sheets` does not exist:

  * The run fails with a clear error.
  * Artifact indicates failure cause under `run.error`.
* If a workbook cannot be opened (corrupt file):

  * The run fails similarly, with an explicit “could not read file” error.

### 8.3 Multiple tables per sheet (future)

The initial implementation can assume **one logical table per sheet**, but
the architecture is compatible with a future where:

* A sheet yields multiple `RawTable` objects, each with its own header/data
  region.
* Table detection logic becomes more sophisticated (e.g., gap‑based segmentation).

When/if this is implemented, it should be documented here and in
`pipeline/extract.py`.

---

## 9. Summary

The IO and table detection layer is responsible for:

1. Turning a `RunRequest` into a **deterministic list of input files**.
2. Streaming **rows** from CSV/XLSX in a memory‑conscious way.
3. Using **config‑provided row detectors** to identify table boundaries and
   emit `RawTable` objects with precise sheet/row metadata.

Everything beyond this point — column mapping, normalization, artifact detail —
is layered on top of these `RawTable`s. If extraction is correct and well
instrumented, the rest of the pipeline can reliably reason about what the
engine “saw” in the original spreadsheets.
```

# apps/ade-engine/docs/04-column-mapping.md
```markdown
# 04 — Column Mapping

Column mapping is the step where `ade_engine` turns a raw worksheet (rows and columns of cells) into a stable, named schema that hooks and downstream systems can rely on.

At a high level:

```text
Workbook / CSV
    ↓
Parsing & row classification (row detectors)
    ↓
Column detection (column detectors)
    ↓
Column mapping
    ↓
Normalized rows exposed to hooks & outputs
```

This document explains:

* What *physical* vs *logical* columns are.
* What inputs column mapping consumes.
* How the mapping is produced and validated.
* How hooks and other parts of the engine use the mapping.
* What guarantees the engine tries to maintain.

---

## Goals

Column mapping is designed to:

1. **Decouple sheet layout from business logic**
   Config packages describe *logical* columns (“invoice_number”, “amount_due”). Column mapping hides whether those live in column B vs column F, or across different sheets.

2. **Provide a stable, named schema for hooks**
   Hooks should work with dictionaries like `{"invoice_number": "...", "amount_due": ...}` instead of worrying about Excel coordinate math.

3. **Allow multiple detection strategies**
   Different column detectors can vote on where a logical column lives. The mapping step combines those signals into a single, deterministic choice.

4. **Fail loudly when required columns are missing**
   If the configuration says a column is required, column mapping is the place where that gets enforced.

5. **Be explainable and debuggable**
   It should be obvious *why* a column was mapped where it was (or why it’s missing) by inspecting logs/artifacts.

---

## Core Concepts

### Physical columns

A **physical column** is “whatever Excel/CSV calls a column”:

* Identified by:

  * `sheet_name` (or index),
  * `column_index` (0‑based) or column letter,
  * and the set of cell values in that column.
* Completely layout‑driven: if the source file changes shape, the physical columns change.

Examples:

* Column `B` on sheet `"Detail"` in an XLSX file.
* Column `0` in a CSV with no sheets.

### Logical columns

A **logical column** is a *semantic* thing defined by the config package, for example:

* `invoice_number`
* `bill_to_name`
* `line_amount`
* `posting_date`

Logical columns:

* Are described in the config manifest (name, type, whether required, etc.).
* Do **not** know where they live in the sheet(s).
* Are the keys hooks and outputs use.

Column mapping’s job is to say:

> “For this document and sheet, logical column `invoice_number` is implemented by physical column B.”

### Detections

**Column detectors** are small pieces of config code that look at the raw sheet and emit *detections* such as:

* “Column B looks like `invoice_number` with score 0.92.”
* “Column F is probably `amount_due` but the header is slightly off.”

Each detection is conceptually:

```text
DetectorFinding:
  logical_column_id   # which logical column this relates to
  sheet_id            # which sheet / tab
  column_index        # which physical column
  score               # confidence or quality signal
  reasons             # optional free‑form explanation / features
```

Different detectors can propose different columns for the same logical column; column mapping resolves these into a single choice.

### Column map

The **column map** is the main output:

```text
ColumnMap:
  sheet_id -> {
    logical_column_id -> MappedColumn
  }

MappedColumn:
  logical_column_id
  sheet_id
  column_index        # chosen physical column
  header_text         # final resolved header (if any)
  detectors           # list of DetectorFinding used
  is_required         # from manifest
  is_satisfied        # True if actually mapped
```

The exact Python types/fields are implementation details, but conceptually this is what the rest of the engine sees.

---

## Inputs to Column Mapping

Column mapping runs once the engine has:

1. **Parsed workbook / CSV**

   * A grid of cells with:

     * raw value,
     * possibly formatted value,
     * row/column indices,
     * sheet metadata.
   * For XLSX, ADE has already chosen which sheet(s) to operate on for this run.

2. **Row classifications (optional but typical)**

   Row detectors may have classified rows as:

   * header row(s),
   * data rows,
   * footer/summary rows,
   * noise (blank, separators, etc.).

   Column detectors can use this to focus on plausible header rows and data samples.

3. **Column detector outputs**

   All column detectors within the active config package have been run. Their findings are aggregated into a common in‑memory representation (as outlined above).

4. **Config manifest schema**

   The manifest describes:

   * the list of logical columns,
   * what they are called,
   * whether they’re required or optional,
   * sometimes hints like expected type/pattern (dates, numbers, strings).

   Column mapping uses this to know *what* to look for and *how strict* to be.

---

## Outputs of Column Mapping

When column mapping completes, the engine has:

1. **A resolved `ColumnMap` per sheet**

   For each sheet being processed:

   * Every logical column from the manifest will have a `MappedColumn` entry.
   * `MappedColumn.is_satisfied` indicates whether a physical column was found.
   * If multiple physical columns were plausible, the chosen winner is recorded along with tie‑breaking details.

2. **Validation results**

   * If required columns are missing, the mapping stage produces structured errors.
   * These can:

     * fail the run early, or
     * be surfaced as warnings depending on engine/config settings.

3. **A normalized row accessor**

   Downstream, hooks receive **normalized rows** that look like:

   ```python
   row["invoice_number"]  # value from whichever physical column was mapped
   ```

   instead of:

   ```python
   row[3]  # pray this is still the invoice number column
   ```

4. **Debug/observer data**

   Mapping decisions are recorded into the run’s debug artifacts (e.g., job/run logs and artifact JSON) so that UIs and developers can understand what happened when a run misbehaves.

---

## Mapping Pipeline

This section describes the mapping algorithm in broad strokes. Many details are implementation‑specific, but the high‑level flow is intentionally stable.

### 1. Candidate generation

For each sheet:

1. The engine enumerates physical columns that are plausible data columns (e.g., non‑empty, not clearly metadata‑only).
2. Each column detector runs and emits zero or more `DetectorFinding` objects.

For a single logical column you might end up with:

```text
logical_column_id = "invoice_number"

Candidates:
  B: score 0.92 (header match: "Invoice #")
  C: score 0.35 (data looks like alphanumeric IDs, header is blank)
  F: score 0.10 (weak pattern match)
```

Detectors can contribute different kinds of evidence:

* header text similarity,
* sample value patterns,
* position relative to other known columns (“amount_due usually appears after quantity”),
* config hints (e.g., “prefer columns named `Invoice #` or `Inv Num`”).

### 2. Scoring and aggregation

The engine then aggregates detector findings:

* Group findings by `(sheet_id, logical_column_id, column_index)`.
* Merge scores from multiple detectors into a **combined score**.

  * E.g., weighted sum, max, or any heuristic the engine uses.
* Normalize scores so they’re comparable across columns.

At this point, for each logical column and sheet, you have a ranked list:

```text
invoice_number:
  B (score 0.92, detectors: header, pattern)
  C (score 0.35, detectors: pattern only)
  F (score 0.10, detectors: weak header match)

amount_due:
  F (score 0.88, detectors: header, numeric)
  G (score 0.20, detectors: numeric)
  ...
```

### 3. Winner selection

For each `(sheet_id, logical_column_id)` pair, the engine chooses:

* The **best candidate** whose score clears a configurable threshold.
* If no candidate meets the threshold, the logical column is **unmapped** on that sheet.

Tie‑breaking typically prefers:

1. Higher combined score.
2. Columns whose headers are “cleaner” matches to the logical column name or its configured aliases.
3. Columns nearer to other high‑confidence columns from the same "family" (e.g., `quantity`, `unit_price`, `amount_due`).

### 4. Building the `ColumnMap`

Once winners are selected:

* For each logical column, create a `MappedColumn`:

  * record `sheet_id`, `column_index`, `header_text`, etc.
  * include the underlying detector findings in case debugging is needed.
* Mark `is_satisfied = True` when a physical column was chosen; `False` otherwise.

The resulting map:

* Is **deterministic** for a given config + document.
* Is **stable** even if detectors are internally refactored, as long as their output semantics stay the same.

### 5. Validation and error reporting

With a `ColumnMap` in hand, the engine validates against the config manifest:

* For each required logical column:

  * If `is_satisfied` is `False`, add a validation error like:

    > `missing_required_column: invoice_number`
* Optionally check expected data types or patterns using sample values from the mapped column (e.g., “95% of values should parse as dates”).

Configuration or runtime settings control whether:

* the run fails fast (“hard” validation), or
* the run continues but reports missing columns as warnings (“soft” validation).

---

## How Hooks Use Column Mapping

Hooks should never need to look at physical row/column indices.

Instead, hooks see **normalized rows** where keys are logical column IDs:

```python
def process_row(row, context):
    # `row` is keyed by logical columns from the config manifest
    invoice_no = row["invoice_number"]
    amount = row["amount_due"]
    posted_at = row.get("posting_date")  # may be None if optional/unmapped

    # Business logic here...
```

This is made possible by column mapping:

1. When the engine streams data rows, it uses the `ColumnMap` to:

   * resolve which physical column(s) provide each logical column value,
   * pull the corresponding cell from the current physical row,
   * optionally coerce/normalize the value (dates, decimals, etc.).
2. The hook receives a **logical view** of the row and never sees raw column indices.

**Important invariants for hooks:**

* The set of keys in `row` matches the logical columns defined in the manifest.
* Missing required columns will normally prevent hooks from running (unless configured otherwise).
* Optional columns may be present but unmapped; in that case their value will typically be `None`.

---

## Multiple Sheets and Tables

ADE’s backend can associate a run with one or more sheets in a workbook:

* Column mapping is **per sheet**:

  * each sheet gets its own `ColumnMap`;
  * hooks may run per sheet or over a combined view, depending on configuration.

Common patterns:

* **Single‑sheet runs**
  The config expects to operate on one sheet (e.g., “Detail”). Column mapping only runs for that sheet.

* **Multi‑sheet runs**
  Some configs may want to:

  * process multiple sheets with the same schema (e.g., monthly tabs), or
  * process different sheets with different schemas (e.g., `Header` vs `Detail` tables).

The column mapping layer is responsible for:

* Ensuring each `(sheet_id, logical_column_id)` is resolved independently.
* Exposing which sheets are “active” for a given run so hooks can iterate accordingly.

---

## Designing Column Detectors for Good Mapping

Column mapping quality is only as good as the signals it receives. When authoring `column_detectors` in a config package:

1. **Prefer clear, narrow responsibilities**

   * One detector can focus on header names.
   * Another can focus on sample data patterns (dates, currency, etc.).
   * A third can use relative position between columns.

2. **Emit scores, not yes/no answers**

   * Use scores to express confidence (0.0–1.0 or similar).
   * Column mapping can then decide how to combine and threshold them.

3. **Explain your decisions**

   * Include brief textual “reasons” in your findings where practical.
   * These surface nicely in logs and make debugging much easier.

4. **Handle noisy real‑world data**

   * Look for common variations in headers (e.g., “Invoice #”, “Inv No”, “Invoice Num”).
   * Be resilient to extra whitespace, casing, and punctuation.

5. **Fail usefully**

   * If a detector is unsure, prefer emitting a low‑confidence candidate rather than nothing.
   * Mapping can drop it based on thresholds, but seeing the candidate in debug output helps diagnostics.

---

## Failure Modes and Debugging

When column mapping goes wrong, you typically see one of:

* Required column reported as missing.
* Hooks throwing `KeyError` for a logical column you expected to be mapped.
* Output files with values shifted or clearly mismatched to their headers.

To debug:

1. **Inspect the run artifact / logs**

   Look at the run’s artifact JSON and/or event log for:

   * The final `ColumnMap`:

     * which physical columns were mapped,
     * any missing required columns.
   * Detector findings:

     * did a detector emit a candidate at all?
     * what score did it assign?

2. **Compare the manifest to the sheet**

   * Is the logical column defined with the name/aliases you expect?
   * Did the header wording in the file change (e.g., from “Invoice #” to “Invoice ID”)?

3. **Check thresholds / configuration**

   * If a candidate has a decent but not great score, perhaps the detection threshold is too strict.
   * Conversely, if the mapping is clearly wrong, thresholds may be too loose.

4. **Refine detectors**

   * Add or adjust detectors to better handle the new layout.
   * Add more robust header and pattern matching.

---

## Summary

Column mapping is the bridge between raw spreadsheet shape and the logical schema your config package defines. It:

* combines signals from `column_detectors`,
* chooses a single physical column for each logical column,
* enforces required vs optional columns,
* and presents hooks with simple, named `row["logical_column"]` access.

As long as you think in terms of *logical columns* and keep column detectors focused and expressive, the engine can adapt to messy, real‑world spreadsheets while keeping your hooks and outputs stable.
```

# apps/ade-engine/docs/05-normalization-and-validation.md
```markdown
# Normalization & Validation

This document describes the **normalization stage** of the ADE engine: how we
turn a `MappedTable` (columns → canonical fields) into:

- a dense, ordered matrix of normalized values, and  
- a structured list of validation issues,

wrapped in a `NormalizedTable`.

This stage is implemented in `pipeline/normalize.py` and sits between:

- **mapping** (`MappedTable`) and  
- **write** (`write_workbook`, which turns `NormalizedTable`s into Excel output).

It assumes you’ve read:

- `03-io-and-table-detection.md` (how we get `RawTable`), and  
- `04-column-mapping.md` (how we get `MappedTable`).

---

## 1. Role in the pipeline

High-level view:

```text
RawTable
  └─(mapping)─▶ MappedTable
                    └─(normalization)─▶ NormalizedTable
                                              └─(write)─▶ Excel workbook
````

**Mapping** answers: *“Which input columns correspond to which canonical fields?”*
**Normalization** answers: *“Given those fields, what are the cleaned values, and are they valid?”*

Normalization is:

* **Config-driven** — transforms and validators live in `ade_config`.
* **Row-oriented** — runs field-by-field for each input row.
* **Pure pipeline** — no IO; just data transformation plus logging/artifact updates.

---

## 2. Inputs & outputs

### 2.1 Function signature

The normalization stage is encapsulated by:

```python
def normalize_table(
    ctx: RunContext,
    cfg: ConfigRuntime,
    mapped: MappedTable,
    logger: PipelineLogger,
) -> NormalizedTable:
    ...
```

Where:

* `ctx: RunContext`

  * Per-run context (paths, manifest, env, metadata, shared `state` dict, timestamps).
* `cfg: ConfigRuntime`

  * Config runtime object exposing:

    * manifest (`ManifestContext`),
    * column registry (`ColumnModule`s with transform/validate),
    * writer defaults, etc.
* `mapped: MappedTable`

  * Output of the mapping stage:

    * `raw: RawTable`
    * `mapping: list[ColumnMapping]`
    * `extras: list[ExtraColumn]`
* `logger: PipelineLogger`

  * Unified logging/telemetry/artifact helper.

Returns:

* `NormalizedTable`

  * `mapped` — original `MappedTable`
  * `rows` — 2D list of normalized values
  * `issues` — list of `ValidationIssue`

---

## 3. Canonical row model

The core internal abstraction is a **canonical row dict**:

```python
row: dict[str, Any]   # field_name -> value
```

This is what transforms and validators read and modify.

### 3.1 Column ordering & enabled fields

Column order comes from the manifest:

* `manifest.columns.order` — ordered list of canonical field names.
* `manifest.columns.meta[field_name].enabled` — flag to include/exclude a field.

Normalization respects that order:

* **Canonical fields**:

  * Iterate over `columns.order` and include only fields where `enabled=True`.
* **Extra columns**:

  * Appended later (based on `MappedTable.extras`), after all canonical fields.

The final `NormalizedTable.rows` is ordered as:

```text
[c1, c2, ..., cN, extra1, extra2, ...]
```

where `c1..cN` follow `columns.order` and `extra*` follow `MappedTable.extras`.

### 3.2 Seeding the canonical row

For each data row in `mapped.raw.data_rows`:

1. Start with an empty `row: dict[str, Any]`.
2. For each canonical field in `manifest.columns.order`:

   * Find its `ColumnMapping` in `mapped.mapping` (if any).
   * If mapped:

     * Read the raw cell from `mapped.raw.data_rows[row_idx][mapping.index]`.
     * Set `row[field_name] = raw_value`.
   * If not mapped:

     * Set `row[field_name] = None` or a manifest-specified default if we
       introduce such behavior.
3. At this point, `row` contains **raw, unnormalized** values keyed by canonical
   field name (and no extras yet).

This seeded `row` is the input to the transform phase.

### 3.3 Row index semantics

`row_index` is always aligned to the **original sheet row index**:

* `MappedTable.raw.header_index` is the header row’s 1-based index.
* Data row `i` is at original row index:

```python
row_index = mapped.raw.first_data_index + i
```

This index is passed into transforms and validators and appears in
`ValidationIssue.row_index` and artifact records.

---

## 4. Transform phase

Transforms are **field-level functions** that clean and normalize data. They
live in `ade_config.column_detectors.<field_module>` and are optional.

### 4.1 Transformer signature

Standard keyword-only signature:

```python
def transform(
    *,
    job,                    # RunContext (named "job" for historical reasons)
    state: dict,            # shared per-run scratch space
    row_index: int,         # original sheet row index (1-based)
    field_name: str,        # canonical field
    value,                  # current value for this field
    row: dict,              # full canonical row (field -> value)
    field_meta: dict | None,
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> dict | None:
    ...
```

Parameters to remember:

* `job`: full run context (paths, metadata, env).
* `state`: mutable dict shared across all rows and scripts within this run.
* `row_index`: traceability back to original file.
* `field_name`, `value`, `row`: the core of the normalization work.
* `field_meta`: the manifest’s metadata for this field (e.g., label, required).
* `env`: config‑level environment values (locale, date formats, etc.).
* `logger`: use for notes/events (not `print`).

### 4.2 Call order & data flow

For each data row:

1. Build the **seed** canonical row as described in §3.2.
2. Iterate over canonical fields in `manifest.columns.order`:

   * For each field with a transformer:

     * Call `transform(...)` with the current `row[field]` and full `row` dict.
     * Allow the transformer to:

       * mutate `row[field]` and/or other `row` entries, and/or
       * return a dict of updates to merge into `row`.

This means:

* Transforms see the **latest state of the row** (including effects of earlier
  transforms in the same row).
* Ordering is deterministic and known: manifest order.

Because of this, config authors can:

* Treat each transform as independent (preferred), or
* Rely on left‑to‑right dependencies (e.g., parse a “full_name” before splitting
  into first/last names).

### 4.3 Return value behavior

* If `transform` returns `None`:

  * The engine assumes all updates were made in-place via `row[...] = ...`.

* If it returns a `dict`:

  * The engine merges it into `row`:

    ```python
    updates = transform(...)
    if updates:
        row.update(updates)
    ```

* Keys in `updates` that are **not** canonical fields:

  * Are allowed (e.g., to compute helper values for validators).
  * They will not appear in the final output unless later mapped by manifest.

### 4.4 Error handling

If a transformer raises an exception:

* The engine treats it as a **config error**:

  * Normalization for that table (and thus run) fails.
  * Artifact’s `run.status` -> `"failed"`, error recorded with script context.
  * Telemetry emits a `run_failed` or similar event.
* Best practice for config authors:

  * Fail fast with clear error messages when assumptions are violated.
  * Avoid catching and hiding exceptions unless truly recoverable.

---

## 5. Validation phase

Validators check **business rules** and produce structured issues. They also
live in `ade_config.column_detectors.<field_module>` and are optional.

### 5.1 Validator signature

Standard keyword-only signature:

```python
def validate(
    *,
    job,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_meta: dict | None,
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> list[dict]:
    ...
```

Same parameters as `transform`, but:

* Focus is on reporting issues, not changing `row`.
* Validators are called **after** all transforms for the row have completed.

### 5.2 Validation issue model

Validators return a list of issue dicts, for example:

```python
return [
    {
        "code": "invalid_email_format",
        "severity": "error",
        "message": "Email must look like user@domain.tld",
        "details": {"value": value},
    }
]
```

Recommended keys:

* `code: str` (required)

  * Short, machine- and human-readable identifier.
  * e.g., `"missing_required"`, `"invalid_format"`, `"out_of_range"`.
* `severity: str` (required)

  * e.g., `"error"`, `"warning"`, `"info"`.
* `message: str` (required)

  * Human-friendly explanation, suitable for UI.
* `details: dict` (optional)

  * Arbitrary additional context for debugging or UI.

The engine wraps these into `ValidationIssue` objects, adding:

* `row_index: int` — original sheet row index.
* `field: str` — canonical field.

### 5.3 Validation ordering & scope

* For each row:

  * Transform phase completes first for all fields.
  * Then validators run for each field that defines a validator.
* Validators see the **final normalized row**:

  * They can validate both `value` and cross-field relationships via `row`.
* Cross-row constraints:

  * May be implemented using `state` to collect information across rows
    (e.g., track duplicates) and report issues during or after normalization.
  * For “summary” behavior, `on_run_end` hooks can also be used.

### 5.4 Exceptions in validators

If a validator raises an exception:

* Treated similarly to transformer errors:

  * Run is marked failed.
  * Error details recorded.
* Validators should not raise for normal “invalid data” cases:

  * Those are represented as issue dicts.
  * Exceptions should signal unexpected conditions in config code itself.

---

## 6. NormalizedTable structure

`NormalizedTable` captures the final output for a mapped table:

```python
@dataclass
class NormalizedTable:
    mapped: MappedTable
    rows: list[list[Any]]           # normalized matrix
    issues: list[ValidationIssue]   # all row-level issues
    output_sheet_name: str          # chosen by writer stage
```

### 6.1 Building `rows`

For each data row:

1. After transforms & validators:

   * Build a list of canonical values:

     ```python
     canonical_values = [
         row[field] for field in manifest.columns.order
         if column_meta[field].enabled
     ]
     ```

2. Append extra columns:

   ```python
   extra_values = []
   for extra in mapped.extras:
       col_idx = extra.index  # 0-based raw column index
       extra_values.append(
           mapped.raw.data_rows[row_offset][col_idx]
       )
   ```

3. Final row:

   ```python
   output_row = canonical_values + extra_values
   rows.append(output_row)
   ```

Invariants:

* All rows in a `NormalizedTable` have the **same length**.
* Canonical columns always appear in manifest order.
* Extra columns appear in `mapped.extras` order.

### 6.2 Aggregating issues

For each row:

* Collect all issue dicts returned by validators.
* Convert them into `ValidationIssue` objects, adding:

  * `row_index`
  * `field`
* Append them to `NormalizedTable.issues`.

Normalization does **not** decide whether issues are “fatal” or not; it only
records them. Policy decisions (e.g., “fail the job if any `severity="error"`”)
belong in the ADE backend or in hooks.

---

## 7. Artifact & telemetry integration

Normalization is tightly coupled with artifact and telemetry for observability.

### 7.1 Artifact (`artifact.json`)

During or after normalization, the artifact recorder (`ArtifactSink`) receives:

* For each table:

  * Validation issues: written under `tables[*].validation`.
* For each issue:

  * `row_index`, `field`, `code`, `severity`, `message`, `details`.

This provides a human/audit-friendly record of data quality for each run.

### 7.2 Telemetry events (`events.ndjson`)

`PipelineLogger` may also emit telemetry events during normalization, e.g.:

* `validation_issue`:

  * For each issue (or batch) with:

    * `field`, `code`, `row_index`, `severity`, plus file/sheet info.
* `normalization_stats`:

  * Summary counts of rows processed, issues per severity, etc.

The exact event set is flexible, but the pattern is:

* Telemetry → streaming / monitoring.
* Artifact → durable audit and reporting.

---

## 8. Guidance for config authors

### 8.1 Writing good transforms

* Prefer **pure, deterministic** transformations:

  * Same input row → same output row.
* Use `env` and `field_meta` rather than hard-coded constants:

  * Date formats, locales, thresholds, etc.
* Keep transforms **local** when possible:

  * Avoid cross-row dependencies unless you have a clear pattern using `state`.
* Avoid:

  * Network calls per row.
  * Unbounded in-memory structures (e.g., storing all rows in `state`).

### 8.2 Writing good validators

* Use validators to express **business rules**:

  * Required fields: `missing_required`.
  * Format: `invalid_format`.
  * Range checks: `out_of_range`.
* Return structured issue dicts rather than raising exceptions.
* Use `severity` consistently:

  * `error` for rules that should block acceptance.
  * `warning` for suspicious but tolerable situations.
* For cross-field checks:

  * Inspect the full `row` (e.g., “if `end_date` < `start_date`”).
* For cross-row checks:

  * Use `state` to accumulate and check after all rows are seen (or in a
    dedicated pass/hook).

### 8.3 Debugging

* Log via `logger.note(...)` and `logger.event(...)`:

  * Include `row_index`, `field`, and key details.
* Compare:

  * Input workbook → mapped headers (`artifact.mapping`) →
    normalized rows (`NormalizedTable.rows`) →
    validation issues (`artifact.validation`).

---

## 9. Edge cases & future extensions

Some known edge cases and potential future enhancements:

* **No data rows**:

  * A `MappedTable` may have a header but zero data rows.
  * Normalization should produce:

    * `rows = []`,
    * `issues = []`.
* **Completely unmapped tables**:

  * All columns become extras; canonical row has only `None` values.
  * Transform/validate may be skipped for fields with no mapping
    (depending on design choice).
* **Batch-level validation**:

  * Future enhancement:

    * Table-level or run-level validators that operate over entire `NormalizedTable`.
* **Additional outputs**:

  * Future: normalized data exported as CSV/Parquet while keeping current
    `NormalizedTable` and artifact contracts intact.

---

With these concepts and contracts in mind, you should be able to:

* Implement `pipeline/normalize.py` end-to-end, and
* Author robust, testable transform/validator scripts in `ade_config` that
  produce predictable, auditable normalized outputs.
```

# apps/ade-engine/docs/06-artifact-json.md
```markdown
# Artifact JSON (`artifact.json`)

`artifact.json` is the **per‑run audit record** produced by the engine.

It is the primary, structured answer to:

> “Exactly what did the engine do to this set of spreadsheets, and why?”  

Everything else (UI, reports, analytics, AI summarization) should treat
`artifact.json` as the source of truth.

This document defines:

- File location and lifecycle.
- The **schema for artifact v1**.
- How tables, mappings, and validation are represented.
- The invariants consumers can rely on.
- How ADE API is expected to consume it.

---

## 1. File location & lifecycle

### 1.1 Where it lives

For each **engine run** there is exactly **one** artifact file:

- Path: `RunPaths.artifact_path`
- Convention: `<logs_root>/artifact.json`

Where `<logs_root>` is:

- Passed in via `RunRequest.logs_root`, or
- Inferred by the engine from the input location (see runtime docs).

### 1.2 When it’s created and updated

The `FileArtifactSink` in `artifact.py` manages the lifecycle:

1. **Start of run**  
   - Creates an in‑memory artifact structure with:
     - Run metadata (`run.status="running"`, `run.run_id`, `run.started_at`, …).
     - Config metadata (`config.schema`, `config.manifest_version`, …).
     - Empty `tables` and `notes` arrays.

2. **During the run**
   - Each pipeline stage calls into the artifact sink:
     - `record_table(...)` to append table summaries.
     - `note(...)` to append human‑oriented notes.
   - This can happen multiple times (e.g., once per table).

3. **On completion (success or failure)**
   - `mark_success(outputs=...)` or `mark_failure(error=...)`:
     - Sets `run.status`.
     - Sets `run.completed_at`.
     - Writes outputs or error info.
   - `flush()` writes JSON to disk **atomically**:
     - Serialize to `artifact.json.tmp`.
     - `fsync` and rename to `artifact.json`.

### 1.3 Guarantees

For **every** engine run (even failed ones):

- `artifact.json` exists at `RunPaths.artifact_path`.
- It is well‑formed JSON.
- `run.status` is either `"succeeded"` or `"failed"`.

---

## 2. Design goals

The artifact schema is intentionally:

- **Human‑inspectable**  
  Easy to read in an editor or pretty‑printed for debugging.

- **Stable & versioned**  
  Changes are additive where possible; breaking changes bump `artifact_version`.

- **Downstream friendly**  
  ADE API, reporting, and AI agents can:
  - Reconstruct mapping decisions.
  - Count validation issues by field/code/severity.
  - See how many tables were processed and from which sheets.

- **Job‑agnostic**  
  No first‑class job concept. Backend can pass `job_id`, `config_id`, etc.
  via `RunRequest.metadata`; the engine stores them under `run.metadata`
  without understanding them.

---

## 3. Top‑level schema (v1)

Artifact JSON v1 has this high‑level shape:

```jsonc
{
  "schema": "ade.artifact/v1",
  "artifact_version": "1.0.0",

  "run": { ... },
  "config": { ... },
  "tables": [ ... ],
  "notes": [ ... ]
}
````

### 3.1 Types and conventions

Across the schema:

* All timestamps are **ISO 8601** strings in UTC (e.g. `"2024-01-01T12:00:00Z"`).
* File paths in `outputs` are strings relative to whatever the worker passes
  into the engine; they are **not** normalized to any global root.
* Optional fields are omitted or set to `null` (never the empty string) when
  not applicable.

Everything in this document refers to **artifact schema v1**:
`"schema": "ade.artifact/v1", "artifact_version": "1.0.0"`.

---

## 4. `run` section

Run‑level metadata and outcome:

```jsonc
"run": {
  "run_id": "run-uuid",
  "status": "succeeded",
  "started_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:00:05Z",
  "outputs": [
    "normalized.xlsx"
  ],
  "metadata": {
    "job_id": "optional-job-id",
    "config_id": "config-abc",
    "workspace_id": "ws-123",
    "any_other_tags": "..."
  },
  "error": null
}
```

### 4.1 Fields

* `run_id: str`
  Unique per engine run (generated by the engine).

* `status: "succeeded" | "failed"`
  Final outcome of the run.

* `started_at: str`
  Time run started (pipeline initialization) in UTC.

* `completed_at: str | null`
  Time run completed (success or failure).
  May be `null` if an unrecoverable error occurs before the engine can set it
  (but the artifact file will still be valid JSON).

* `outputs: string[]`
  Paths (usually file names) of output workbooks written by the engine.
  Typically length 1, but future writer modes may emit more.

* `metadata: object`
  Opaque copy of `RunContext.metadata`.
  The engine does not interpret these keys, but they are intended for:

  * `job_id`
  * `config_id`
  * `workspace_id`
  * any other backend correlation tags.

* `error: object | null`
  If `status == "failed"`, contains error summary.
  Recommended shape:

  ```jsonc
  {
    "type": "EngineError | ConfigError | InputError | HookError | ...",
    "message": "Human-readable summary",
    "details": {
      "exception_type": "ValueError",
      "exception_message": "...",
      "stage": "extracting | mapping | normalizing | writing_output | hooks"
    }
  }
  ```

Backend **must not** rely on any specific error subtype values; treat them as
best‑effort hints.

---

## 5. `config` section

Metadata about the config and manifest used for the run:

```jsonc
"config": {
  "schema": "ade.manifest/v1.0",
  "manifest_version": "1.2.3",
  "title": "My Config Name"
}
```

### 5.1 Fields

* `schema: str`
  Manifest schema tag, e.g. `"ade.manifest/v1.0"`.

* `manifest_version: str`
  Value of `info.version` from `manifest.json` (semver recommended).

* `title: str | null`
  Human‑readable name from `manifest.info.title`, or `null` if not provided.

This section lets you answer “which config produced this artifact?” quickly,
without opening the manifest.

---

## 6. `tables` section

Each element in `tables` describes one logical table detected in the input:

```jsonc
"tables": [
  {
    "input_file": "input.xlsx",
    "input_sheet": "Sheet1",
    "header": {
      "row_index": 5,
      "cells": ["ID", "Email", "..."]
    },
    "mapping": [
      {
        "field": "member_id",
        "header": "ID",
        "source_column_index": 0,
        "score": 0.92,
        "contributions": [
          {
            "detector": "ade_config.column_detectors.member_id.detect_header_synonyms",
            "delta": 0.60
          },
          {
            "detector": "ade_config.column_detectors.member_id.detect_value_shape",
            "delta": 0.32
          }
        ]
      }
    ],
    "unmapped": [
      {
        "header": "Notes",
        "source_column_index": 5,
        "output_header": "raw_notes"
      }
    ],
    "validation": [
      {
        "row_index": 10,
        "field": "email",
        "code": "invalid_format",
        "severity": "error",
        "message": "Email must look like user@domain.tld",
        "details": {
          "value": "foo@",
          "pattern": ".*@.*\\..*"
        }
      }
    ]
  }
]
```

### 6.1 Per‑table metadata

* `input_file: str`
  Basename of the input file where the table was found
  (e.g., `"input.xlsx"` or `"members.csv"`).

* `input_sheet: str | null`
  Excel sheet name, or `null` for CSV.

* `header: object`

  * `row_index: int` — 1‑based row index within the sheet.
  * `cells: string[]` — header row cells as strings.

The **table identity** is implicitly `(input_file, input_sheet, header.row_index)`.

### 6.2 `mapping` entries

Each item describes how one canonical field was mapped:

* `field: str`
  Canonical field name (from manifest `columns.meta`).

* `header: str`
  Original header text from the input file that was mapped to this field
  (post simple normalization).

* `source_column_index: int`
  Zero‑based index of the column in the raw table.

* `score: number`
  Final matching score for this `(field, column)` after aggregating detector
  contributions.

* `contributions: {detector, delta}[]`
  Fine‑grained breakdown of how `score` was built:

  * `detector: str` — fully qualified function name or a stable ID.
  * `delta: number` — contribution added by that detector.

This structure makes it possible to reconstruct **why** a column mapped to a
field, not just that it did.

### 6.3 `unmapped` entries

Each `unmapped` entry represents an input column that was not mapped to any
canonical field but is preserved in the normalized output:

* `header: str`
  Original header text.

* `source_column_index: int`
  Zero‑based index in the raw table.

* `output_header: str`
  Generated header used for this column in the normalized workbook
  (e.g. `raw_notes`), based on writer settings.

If `engine.writer.append_unmapped_columns` is `false` in the manifest, the
engine may omit `unmapped` entries (or leave the array empty) because those
columns are dropped entirely.

### 6.4 `validation` entries

Each validation issue is recorded **per field, per row**:

* `row_index: int`
  1‑based original row index in the sheet (consistent with extraction).

* `field: str`
  Canonical field name.

* `code: str`
  Short, machine‑friendly identifier, e.g. `"invalid_format"`,
  `"missing_required"`, `"out_of_range"`.

* `severity: str`
  At least:

  * `"error"`
  * `"warning"`
    Additional severities may be defined later (e.g. `"info"`).

* `message: str`
  Human‑readable explanation suitable for UI display.

* `details: object | null`
  Optional structured data to support richer UIs:

  * e.g. `{ "expected_pattern": "...", "actual_value": "..." }`.

The engine normalizes any issues returned by validators into this shape before
writing the artifact.

---

## 7. `notes` section

`notes` is a human‑oriented timeline of important events or comments:

```jsonc
"notes": [
  {
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "info",
    "message": "Run started",
    "details": {
      "input_files": 1,
      "config": "config-abc"
    }
  }
]
```

### 7.1 Fields

Each note entry contains:

* `timestamp: str`
  When the note was recorded.

* `level: "debug" | "info" | "warning" | "error"`
  Severity or importance of the note.

* `message: str`
  Human‑readable text.

* `details: object | null`
  Optional structured data (free‑form).

### 7.2 Sources of notes

Notes may be produced by:

* The engine itself:

  * Phase transitions, key milestones.
* Hooks:

  * `on_run_start`, `on_after_extract`, `on_after_mapping`, etc.
* Config scripts:

  * Via the provided `artifact` or `logger` APIs (used sparingly for enduring
    notes; otherwise prefer telemetry).

**Guideline:**

Use `notes` for high‑level narrative. Use telemetry (`events.ndjson`) for
more granular event streams.

---

## 8. Behavior & invariants

The following **invariants** hold for artifact v1:

* `run.status ∈ {"succeeded", "failed"}`.
* When `status == "succeeded"`:

  * `run.outputs` has at least one entry.
* When `status == "failed"`:

  * `run.error` is non‑null and contains a `message`.
* For every table:

  * `input_file` is non‑empty string.
  * `header.row_index ≥ 1`.
  * `header.cells` length equals `mapping.length + unmapped.length` if the
    writer is configured to preserve all columns.
* `tables`, `mapping`, `unmapped`, `validation`, `notes` are arrays;
  missing values are represented as empty arrays, not `null`.

Backends can safely rely on these when building UI and reporting logic.

---

## 9. Versioning & evolution

Artifact is explicitly versioned via:

* `schema` — identifies the “family” (e.g., `"ade.artifact/v1"`).
* `artifact_version` — semantic version for this family.

### 9.1 Backwards‑compatible changes

Allowed without bumping `schema` and with minor/patch bumps of
`artifact_version`:

* Adding optional fields.
* Adding `details` sub‑fields.
* Adding new `code` / `severity` values.

Consumers should ignore unknown fields.

### 9.2 Breaking changes

Require either:

* A new `schema` (e.g. `"ade.artifact/v2"`), or
* A major bump in `artifact_version` and clear migration plan.

Breaking changes include:

* Removing or renaming top‑level keys.
* Changing the meaning or type of existing fields.
* Changing how tables are keyed or identified.

---

## 10. How ADE API should use `artifact.json`

Typical usage patterns:

* **Job summary page**

  * Use `run.status`, `run.error`, and `run.outputs`.
  * Show config `title` and `manifest_version`.

* **Field mapping explanation**

  * For each table:

    * Show `mapping` rows: canonical field → input header + score.
    * Show `unmapped` columns and their generated `output_header`.

* **Data quality reporting**

  * Aggregate `validation` entries across tables:

    * counts by `field`, `code`, `severity`.
    * top rows with many issues.
  * Provide drill‑down views: “show me all rows where `member_id` is missing”.

* **AI‑assisted explanations**

  * Use `tables[*].mapping`, `validation`, `notes`, and `run.metadata` as the
    primary context to explain:

    * how the engine interpreted the file,
    * what problems were found,
    * how severe they are.

`events.ndjson` (telemetry) complements `artifact.json` with a fine‑grained
event stream, but `artifact.json` is the canonical, stable run summary.
```

# apps/ade-engine/docs/07-telemetry-events.md
```markdown
# Telemetry Events

This document describes the **telemetry event system** used by the ADE engine:
how events are modeled, written, filtered, and consumed via `events.ndjson`.

It focuses on the **event stream**, not on `artifact.json`. For the artifact
schema, see `06-artifact-json.md`.

---

## 1. Goal and mental model

Telemetry answers: **“What happened, in what order, with what context?”**

- It is:
  - **Append-only** — a time-ordered stream of small JSON envelopes.
  - **Per-run** — one NDJSON file per engine run.
  - **Configurable** — extra sinks can be plugged in (e.g. message bus).
- It is *not*:
  - A full audit snapshot (that’s `artifact.json`).
  - A durable state store or metrics DB.

The engine writes telemetry via a small set of APIs and abstractions:

- **Data model**: `TelemetryEvent`, `TelemetryEnvelope`.
- **Runtime wiring**: `TelemetryConfig`, `TelemetryBindings`.
- **Output**: `EventSink` implementations (`FileEventSink`, `DispatchEventSink`).
- **Public facade**: `PipelineLogger` (what pipeline and config code use).

---

## 2. Telemetry vs. artifact

The engine produces two complementary outputs:

- **`artifact.json`** — structured, run-level snapshot:
  - Mapping decisions, validation issues, table metadata, notes.
  - Optimized for **post-run inspection and reporting**.

- **`events.ndjson`** — line-based event stream:
  - `run_started`, `pipeline_transition`, `file_processed`,
    `validation_issue`, `run_failed`, etc.
  - Optimized for **streaming**, **log aggregation**, and **near-real-time UI**.

Most data is visible in both, but:

- Artifact is **hierarchical and consolidated**.
- Telemetry is **fine-grained and chronological**.

---

## 3. Data model

### 3.1 TelemetryEvent

An individual event emitted by the engine, modeled in
`ade_engine.schemas.telemetry` (Pydantic).

Conceptual fields:

- `event: str`  
  Short name, e.g. `"run_started"`, `"file_processed"`,
  `"pipeline_transition"`, `"validation_issue"`.
- `level: str`  
  One of `"debug" | "info" | "warning" | "error" | "critical"`.
- `payload: dict[str, Any]`  
  Event-specific data, e.g.:

  ```jsonc
  {
    "event": "file_processed",
    "level": "info",
    "payload": {
      "file": "input.xlsx",
      "table_count": 3
    }
  }
````

The event name and level are always present; the payload is free-form, but
should be **small, self-contained, and JSON-friendly**.

### 3.2 TelemetryEnvelope

Every event is wrapped in an envelope with run context and timestamps.

Modeled as e.g. `TelemetryEnvelope` in `ade_engine.schemas.telemetry`:

* `schema: str`
  Schema tag, e.g. `"ade.telemetry/run-event.v1"`.
* `version: str`
  Version of the telemetry schema.
* `run_id: str`
  The engine’s internal run ID (`RunContext.run_id`).
* `timestamp: str`
  ISO 8601 UTC timestamp of when the event was emitted.
* `metadata: dict[str, Any]`
  Optional subset of `RunContext.metadata`, e.g.:

  * `job_id`
  * `config_id`
  * `workspace_id`
* `event: TelemetryEvent`

Example envelope (one line in `events.ndjson`):

```json
{
  "schema": "ade.telemetry/run-event.v1",
  "version": "1.0.0",
  "run_id": "run-uuid-1234",
  "timestamp": "2024-01-01T12:34:56Z",
  "metadata": {
    "job_id": "job-abc",
    "config_id": "config-1.2.3"
  },
  "event": {
    "event": "file_processed",
    "level": "info",
    "payload": {
      "file": "input.xlsx",
      "table_count": 3
    }
  }
}
```

---

## 4. Event sinks

### 4.1 EventSink protocol

Internally, sinks implement a minimal interface (conceptual):

```python
class EventSink(Protocol):
    def log(
        self,
        event: str,
        *,
        job: RunContext,
        level: str = "info",
        **payload: Any,
    ) -> None:
        ...
```

Responsibilities:

* Construct `TelemetryEvent` and wrap it in a `TelemetryEnvelope`.
* Decide whether to emit the event (e.g. filter by level).
* Write or forward it to the appropriate backend (file, bus, etc).

### 4.2 FileEventSink

Default sink used by the engine.

* Writes **one JSON envelope per line** to:

  ```text
  <logs_root>/events.ndjson
  ```

* Behavior:

  * Opens file in append mode.
  * Serializes the envelope to JSON.
  * Writes a single line per event.

* Guarantees:

  * Events are appended in the order they are emitted.
  * If no events are emitted, the file still exists (may be empty).

### 4.3 DispatchEventSink

Composite sink that fans out events to multiple sinks.

* Holds a list of child `EventSink` instances.
* On `log(...)`, forwards the event to each child.
* Typical usage:

  * File + console logs.
  * File + HTTP/queue sink in a worker environment.

---

## 5. TelemetryConfig and bindings

### 5.1 TelemetryConfig

`TelemetryConfig` is passed to `Engine.__init__` and controls how telemetry
behaves for that engine instance.

Conceptual fields:

* `correlation_id: str | None`
  Optional out-of-band correlation ID (e.g., from the worker/job system).
* `min_event_level: str`
  Minimum severity for events to be emitted (e.g. `"info"`).
* `event_sink_factories: list[Callable[[RunContext], EventSink]]`
  Factories to build sinks for each run.

Intent:

* Configure **once** at engine construction.
* Keep **run-specific data** (paths, run_id, metadata) in `RunContext`, not in
  the config.

### 5.2 TelemetryBindings

For each run, the engine creates `TelemetryBindings`:

* Holds:

  * `events: EventSink` — already wired to `<logs_root>/events.ndjson` and any
    additional sinks.
  * `artifact` sink — for structured notes (see `artifact.json` doc).
* Decorates events with:

  * `run_id`, `metadata`, timestamps, schema tags.

`TelemetryBindings` is attached to `RunContext` (directly or indirectly) and is
used by `PipelineLogger` to emit events and notes.

---

## 6. PipelineLogger

`PipelineLogger` is the **single entry point** that pipeline code and config
scripts should use for logging and telemetry.

### 6.1 API

Conceptually:

```python
class PipelineLogger:
    def note(self, message: str, level: str = "info", **details: Any) -> None: ...
    def event(self, name: str, level: str = "info", **payload: Any) -> None: ...
    def transition(self, phase: str, **payload: Any) -> None: ...
    def record_table(self, table_summary: dict[str, Any]) -> None: ...
```

* `note(...)`

  * Writes a human-friendly note into the artifact’s `notes` list.
  * May also emit a telemetry event (depending on config).
* `event(...)`

  * Emits a structured telemetry event only (`TelemetryEvent`/`TelemetryEnvelope`).
* `transition(...)`

  * Convenience helper that emits a `pipeline_transition` event with:

    * `phase` and extra details (file counts, table counts, etc).
* `record_table(...)`

  * Records table mapping/validation summary into the artifact and may emit a
    telemetry event summarizing the table.

### 6.2 Usage guidelines

* **Engine internals**:

  * Use `transition` at stage boundaries.
  * Use `event` for specific meaningful events.
  * Use `note` for human-readable context in the artifact.
* **Config scripts & hooks**:

  * Prefer `logger.event(...)` for custom structured events (e.g. scoring or
    business-quality metrics).
  * Use `logger.note(...)` for narrative context that should appear in the
    artifact (e.g. “Detected unusual member ID patterns”).

---

## 7. NDJSON output

### 7.1 File location

Telemetry is written to:

```text
<logs_root>/events.ndjson
```

where `logs_root` is determined from `RunRequest` / `RunPaths`.

### 7.2 Format guarantees

* Each line is a **single complete JSON object** (a `TelemetryEnvelope`).
* Lines are separated by `\n` with no trailing comma.
* Consumers can treat the file as a standard NDJSON stream.

### 7.3 Example (abridged)

```text
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"run_started","level":"info","payload":{...}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"pipeline_transition","level":"info","payload":{"phase":"extracting","file_count":1}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"file_processed","level":"info","payload":{"file":"input.xlsx","table_count":2}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run-1",...,"event":{"event":"run_completed","level":"info","payload":{"status":"succeeded"}}}
```

The exact payload shape varies by event name, but all share the same envelope.

---

## 8. Standard events

The engine emits a small, consistent set of event types. Configs may add more,
but should avoid redefining these.

### 8.1 Core lifecycle

* `run_started`
  Emitted once at run start.

  Payload (typical):

  * `engine_version`
  * `config_version`
  * basic input summary (e.g. file count)

* `run_completed`
  Emitted once on successful completion.

  Payload:

  * `status: "succeeded"`
  * `duration_ms`
  * optional row/table counts

* `run_failed`
  Emitted once on failure.

  Payload:

  * `status: "failed"`
  * `error_type`
  * `error_message`

### 8.2 Pipeline transitions

* `pipeline_transition`
  Emitted when the pipeline moves between phases:

  * `"extracting"`
  * `"mapping"`
  * `"normalizing"`
  * `"writing_output"`
  * `"completed"`
  * `"failed"`

  Payload (typical):

  * `phase`
  * optional counters (e.g. `file_count`, `table_count`)

### 8.3 File and table events

* `file_discovered`
  Emitted when an input file is discovered (optional).

* `file_processed`
  Emitted after a file has been fully processed.

  Payload:

  * `file`
  * `table_count`

* `table_detected`
  Emitted after a `RawTable` is constructed.

  Payload:

  * `file`
  * `sheet`
  * `header_row_index`
  * `data_row_count`

### 8.4 Validation and quality

* `validation_issue`
  Optional per-issue or per-row event.

  Payload (typical):

  * `file`
  * `sheet`
  * `row_index`
  * `field`
  * `code`
  * `severity`

Configs may:

* Emit their own domain-specific events (e.g. `quality_score_computed`).
* Use these standard events to align with ADE backend expectations.

---

## 9. Consumption by ADE backend

Typical backend workflows:

* **Batch ingestion**:

  * Parse `events.ndjson` after run completion.
  * Derive metrics (e.g. total rows processed, error rates).
  * Store data in a log index or metrics system.

* **Streaming / UI**:

  * Tail `events.ndjson` (or equivalent stream in workers).
  * Push events into a websocket or UI log.
  * Show progress as phases change and files/tables are processed.

The engine does not know where or how events are consumed; it just writes
envelopes to the configured sinks.

---

## 10. Best practices and extensibility

### 10.1 For engine maintainers

* Keep the **set of standard event names small and stable**.
* When changing envelope or payload structure:

  * Prefer additive changes.
  * For breaking changes, bump the telemetry schema `version`.
* Ensure `events.ndjson` is always created and valid, even on early failures.

### 10.2 For config authors

* Use `logger.event(...)` for custom events instead of ad-hoc printing.
* Keep payloads:

  * Small,
  * JSON-serializable,
  * Stable (avoid putting huge blobs or entire rows in telemetry).

### 10.3 For backend integrators

* Treat `events.ndjson` as a **log source**, not a permanent store.
* Use:

  * Artifact for detailed, structured reporting.
  * Telemetry for progress, alerts, and coarse metrics.
* When adding custom sinks (via `TelemetryConfig`):

  * Ensure they are **non-blocking** or have appropriate backpressure.
  * Handle network/IO errors gracefully (do not crash the run).

With these conventions, telemetry stays predictable, useful, and easy to
consume without complicating the core engine.
```

# apps/ade-engine/docs/08-hooks-and-extensibility.md
```markdown
# Hooks & Extensibility

This document describes the **hook system** that lets `ade_config` plug custom
logic into well‑defined points of an ADE engine run, without changing the
engine core.

Hooks are how configs:

- add custom reporting,
- adjust tables or mappings,
- decorate the final workbook,
- emit metrics or integrate with external systems.

It assumes you’ve read the top‑level `README.md` and have a basic picture of
the pipeline (`extract → mapping → normalize → write`).

---

## 1. Mental model

At a high level:

- Each engine run has a single **`RunContext`** (`job` in script APIs).
- The engine executes the pipeline in phases.
- At certain phases, it calls **hook functions** defined in `ade_config.hooks`.
- Hooks receive:
  - the current `RunContext`,
  - shared per‑run `state` dict,
  - the manifest and `env`,
  - artifact and telemetry sinks,
  - and phase‑specific objects (tables, workbook, result).

Hooks are **config‑owned**:

- The engine defines *when* hooks are called and *what* data they see.
- The config defines *what* those hooks do.

There is no global/shared state between runs; hooks only see per‑run state
through `RunContext` and `state`.

---

## 2. Hook stages (lifecycle)

The engine exposes five hook stages. They are configured in the manifest and
invoked in this order:

| Stage name        | When it runs                                       | What is available / allowed to change                                  |
| ----------------- | -------------------------------------------------- | ----------------------------------------------------------------------- |
| `on_run_start`    | After manifest + telemetry initialized, before IO | Read/initialize `state`, add notes, never touches tables or workbook    |
| `on_after_extract`| After `RawTable[]` built, before column mapping   | Inspect/modify `RawTable` objects                                       |
| `on_after_mapping`| After `MappedTable[]` built, before normalization | Inspect/modify `MappedTable` objects (mappings and extras)              |
| `on_before_save`  | After `NormalizedTable[]`, before writing files   | Inspect `NormalizedTable[]`, modify `Workbook` (formatting, summary)    |
| `on_run_end`      | After run success/failure determined              | Inspect `RunResult`, emit metrics/notes, **no further pipeline changes** |

Key points:

- Hooks in a stage run **sequentially, in manifest order**.
- `on_run_start` and `on_run_end` are for run‑level concerns only.
- `on_after_extract` / `on_after_mapping` / `on_before_save` may **mutate**
  objects they receive, as long as they keep them structurally valid.

---

## 3. Config & manifest wiring

Hooks are configured in the `hooks` section of `manifest.json`.

### 3.1 Manifest structure

Example:

```jsonc
{
  "hooks": {
    "on_run_start": [
      { "script": "hooks/on_run_start.py", "enabled": true }
    ],
    "on_after_extract": [
      { "script": "hooks/on_after_extract.py" }
    ],
    "on_after_mapping": [
      { "script": "hooks/on_after_mapping.py" }
    ],
    "on_before_save": [
      { "script": "hooks/on_before_save.py" }
    ],
    "on_run_end": [
      { "script": "hooks/on_run_end.py" }
    ]
  }
}
````

Rules:

* Stage keys (`on_run_start`, `on_after_extract`, etc.) are **optional**:

  * Omitted stage → no hooks for that stage.
* Each entry:

  ```jsonc
  { "script": "hooks/on_run_start.py", "enabled": true }
  ```

  * `script` is a path **relative to the `ade_config` package root**.
  * `enabled` is optional; default is `true`.
* Hooks for a stage run in **the array order**.

### 3.2 Script path → module

For each entry:

* `script: "hooks/on_run_start.py"` → module: `ade_config.hooks.on_run_start`
* `script: "hooks/reporting/end_of_run.py"` → module:
  `ade_config.hooks.reporting.end_of_run`

If a hook module cannot be imported, the engine:

* raises a config‑load error (the run fails before pipeline work starts), and
* records a useful error message.

---

## 4. HookRegistry and invocation

Internally, `config_runtime` builds a **`HookRegistry`** from the manifest.

Responsibilities:

* Resolve `script` paths into importable module names.
* Import modules once per run.
* Discover the callable to execute (entrypoint).
* Group hooks by stage (`on_run_start`, `on_after_extract`, etc.) in order.

The pipeline orchestrator then does something conceptually like:

```python
# on_run_start
hooks.call(
    stage="on_run_start",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    logger=pipeline_logger,
)

# on_after_extract
hooks.call(
    stage="on_after_extract",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    tables=raw_tables,
    logger=pipeline_logger,
)

# on_after_mapping
hooks.call(
    stage="on_after_mapping",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    tables=mapped_tables,
    logger=pipeline_logger,
)

# on_before_save
hooks.call(
    stage="on_before_save",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    tables=normalized_tables,
    workbook=workbook,
    logger=pipeline_logger,
)

# on_run_end
hooks.call(
    stage="on_run_end",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    result=run_result,
    logger=pipeline_logger,
)
```

If a stage has no configured hooks, `HookRegistry` is a no‑op for that stage.

---

## 5. Hook function API

Hook modules are regular Python modules in `ade_config.hooks.*`.

### 5.1 Recommended signature

The engine looks for a **`run` function** with a keyword‑only signature:

```python
def run(
    *,
    job,               # RunContext (called "job" for historical reasons)
    state: dict,
    manifest: dict,
    env: dict | None,
    artifact,          # ArtifactSink
    events,            # EventSink | None
    tables=None,       # stage-dependent: RawTable[] / MappedTable[] / NormalizedTable[]
    workbook=None,     # openpyxl.Workbook for on_before_save
    result=None,       # RunResult for on_run_end
    logger=None,       # PipelineLogger
    **_,
) -> None:
    ...
```

Guidelines:

* Always accept `**_` to remain forward compatible with future parameters.
* Treat `job` as read‑only engine context; use `state` for mutable per‑run data.
* Use `logger` as the primary way to emit notes/events:

  * `logger.note("...", level="info", **details)`
  * `logger.event("...", level="info", **payload)`
* Use `artifact` and `events` only if you need direct sink control.

### 5.2 Optional `HookContext` style

The engine **may** also support a single‑argument style if you prefer:

```python
def run(ctx) -> None:
    # ctx.job, ctx.state, ctx.manifest, ctx.env, ctx.artifact, ctx.events,
    # ctx.tables, ctx.workbook, ctx.result, ctx.logger
    ...
```

This is purely a convenience; the recommended, explicit style is the
keyword‑only function.

---

## 6. What hooks are allowed to mutate

Hooks have real power; this section defines what is safe to mutate at each
stage.

### 6.1 `state`

* `state` is the same dict exposed to detectors, transforms, validators, and
  hooks.
* It is **per run**; no sharing between runs.
* You can freely add, update, or delete keys.
* Typical usage:

  * caches,
  * cross‑table aggregates,
  * counters.

### 6.2 `tables`

* `on_after_extract`:

  * Receives `RawTable[]`.
  * You may:

    * reorder tables,
    * drop tables,
    * tweak header or data rows (e.g., trimming, fixing obvious anomalies).
  * Keep invariants intact:

    * `header_row` and `data_rows` must remain aligned with `header_index`,
      `first_data_index`, `last_data_index`.

* `on_after_mapping`:

  * Receives `MappedTable[]`.
  * You may:

    * override mappings for specific columns,
    * adjust `extras` (`ExtraColumn` list),
    * change field order if your writer mode supports it.
  * Be careful not to introduce holes or duplicates in mapping.

* `on_before_save`:

  * Receives `NormalizedTable[]`.
  * You may:

    * reorder tables for writing,
    * drop tables,
    * (carefully) adjust `issues` collections.
  * Individual row values are usually better handled during normalization,
    not here, but small fixes are allowed if necessary.

### 6.3 `workbook` (on_before_save only)

* `workbook` is an openpyxl `Workbook` that the engine will save after the
  hook stage.
* You may:

  * create new sheets (e.g., summary, readme, metrics),
  * adjust cell formatting, column widths, freeze panes, filters,
  * add formulas or static metadata cells.
* Do **not**:

  * rename or delete sheets created by the engine unless you know exactly how
    the writer behaves,
  * change the shape of existing data ranges in ways that break downstream
    expectations.

### 6.4 `result` (on_run_end only)

* `result` is a `RunResult` instance.
* It is treated as **immutable** by hooks:

  * Do not modify it.
  * Use it only for reporting (e.g., log/telemetry/metrics).

---

## 7. Common patterns (examples)

Below are typical uses of each hook stage.

### 7.1 `on_run_start`: initialize and annotate

```python
# ade_config/hooks/on_run_start.py
def run(*, job, state, manifest, env, artifact, events, logger=None, **_):
    state["start_timestamp"] = job.started_at.isoformat()
    state["config_version"] = manifest["info"]["version"]

    logger.note(
        "Run started",
        config_title=manifest["info"].get("title"),
        config_version=manifest["info"]["version"],
    )
```

### 7.2 `on_after_extract`: table sanity checks

```python
# ade_config/hooks/on_after_extract.py
def run(*, tables, logger, **_):
    for t in tables:
        logger.note(
            "Extracted table",
            file=str(t.source_file),
            sheet=t.source_sheet,
            row_count=len(t.data_rows),
            header_row_index=t.header_index,
        )

        if len(t.data_rows) == 0:
            logger.note(
                "Empty table detected",
                level="warning",
                file=str(t.source_file),
                sheet=t.source_sheet,
            )
```

### 7.3 `on_after_mapping`: tweak ambiguous mappings

```python
# ade_config/hooks/on_after_mapping.py
def run(*, tables, logger, **_):
    for table in tables:
        # Example: ensure at most one "email" mapping
        seen_email = False
        for m in table.mapping:
            if m.field == "email":
                if seen_email:
                    logger.note(
                        "Dropping duplicate email mapping",
                        level="warning",
                        header=m.header,
                        column_index=m.index,
                    )
                    m.field = "raw_email_candidate"
                else:
                    seen_email = True
```

### 7.4 `on_before_save`: add summary sheet

```python
# ade_config/hooks/on_before_save.py
def run(*, tables, workbook, manifest, logger=None, **_):
    summary = workbook.create_sheet(title="ADE Summary")

    summary["A1"] = "Config"
    summary["B1"] = manifest["info"]["title"]
    summary["A2"] = "Version"
    summary["B2"] = manifest["info"]["version"]

    row = 4
    summary[f"A{row}"] = "Table"
    summary[f"B{row}"] = "Rows"
    row += 1

    for t in tables:
        summary[f"A{row}"] = f"{t.mapped.raw.source_file.name}:{t.output_sheet_name}"
        summary[f"B{row}"] = len(t.rows)
        row += 1

    if logger:
        logger.note("Added ADE Summary sheet")
```

### 7.5 `on_run_end`: aggregate metrics

```python
# ade_config/hooks/on_run_end.py
def run(*, job, state, result, artifact, logger=None, **_):
    duration_ms = (job.completed_at - job.started_at).total_seconds() * 1000
    status = result.status

    if logger:
        logger.event(
            "run_summary",
            level="info",
            status=status,
            duration_ms=duration_ms,
            processed_files=list(result.processed_files),
        )

    artifact.note(
        f"Run {status} in {duration_ms:.0f}ms",
        level="info",
    )
```

---

## 8. Error handling & safety

### 8.1 Effect of exceptions

* Any uncaught exception in a hook:

  * marks the run as **failed**,
  * records a `HookExecutionError` (or equivalent) in artifact/telemetry,
  * stops further pipeline work.

The engine **does not** swallow hook errors silently.

### 8.2 Best practices

* Validate your assumptions early and fail fast with clear messages if they
  are violated.
* If you depend on external systems (HTTP, DB, etc.):

  * handle timeouts and transient failures,
  * decide when to treat them as fatal vs. degraded behavior.
* Prefer `logger.note` / `logger.event` over raw `print` or ad‑hoc logging.

---

## 9. Compatibility & versioning

To keep configs working across versions:

* Hook functions should:

  * use keyword‑only parameters, and
  * always include `**_` to ignore new parameters.
* The engine may add new keyword arguments over time (e.g., additional
  metadata).

Breaking changes to script APIs are coordinated via:

* `config_script_api_version` in the manifest, and
* documentation that describes the new expectations.

When in doubt, check:

* `ade_engine.schemas.manifest.ManifestV1` for the manifest version you
  target, and
* `hooks.py` for any new `HookStage` or context fields.

---

## 10. Hook author checklist

When adding or modifying hooks in a config:

1. **Decide the stage(s)** you need:

   * *Run metadata?* → `on_run_start` / `on_run_end`
   * *Inspect/reshape tables?* → `on_after_extract` / `on_after_mapping`
   * *Workbook styling/reporting?* → `on_before_save`
2. **Add entries to `manifest.json`** under `hooks` with correct `script` paths.
3. **Create hook modules** in `ade_config/hooks/` with a `run(...)` function:

   * use keyword‑only signature,
   * include `**_` for forward compatibility.
4. **Use `logger` for notes/events**, `state` for shared run data.
5. **Mutate only what’s safe** for the stage (see section 6).
6. **Test end‑to‑end**:

   * run the engine locally on sample files,
   * inspect `artifact.json` and `events.ndjson`,
   * verify hooks behave as expected.

With this model, hooks give you powerful extension points while keeping the
core engine small, predictable, and reusable across many configs.
```

# apps/ade-engine/docs/09-cli-and-integration.md
```markdown
# CLI and Integration with ADE API

This document describes the command‑line interface to the ADE engine and how
the ADE backend invokes it inside a virtual environment.

It assumes you’ve read `ade_engine/README.md` and understand that the engine
is **path‑based and job‑agnostic**: it sees input/output/log paths and opaque
metadata, not job IDs or queues.

---

## 1. Goals of the CLI

The CLI is a thin, stable wrapper around `Engine.run()` that:

- Accepts **file system paths and options** as flags.
- Construct a `RunRequest`.
- Executes a single pipeline run.
- Emits a **machine‑readable JSON summary** to stdout.
- Returns a **meaningful exit code**.

It is primarily used by:

- ADE backend workers (processes/threads/containers) running inside
  a config‑specific virtual environment.
- Engineers debugging locally from the terminal.

---

## 2. Entrypoints

The CLI is exposed in two equivalent ways:

- Module entrypoint:

  ```bash
  python -m ade_engine ...
````

* (Optional) console script, if configured in packaging:

  ```bash
  ade-engine ...
  ```

Both forms call `ade_engine.cli.main()`. The CLI **does not** create or manage
virtual environments; it assumes the current interpreter is already running
inside the correct venv (`ade_engine` + the desired `ade_config`).

---

## 3. Argument model

The CLI maps directly to `RunRequest` fields. Conceptually:

```bash
python -m ade_engine \
  [INPUT SELECTION] \
  [OUTPUT / LOGS] \
  [CONFIG OPTIONS] \
  [EXECUTION OPTIONS]
```

### 3.1 Input selection (mutually exclusive)

Exactly one of these must be provided:

* `--input PATH` (repeatable)
  One or more explicit input files:

  ```bash
  --input /data/jobs/123/input/input.xlsx
  --input /data/jobs/123/input/other.xlsx
  ```

  → `RunRequest.input_files = [Path(...), Path(...)]`

* `--input-root DIR`
  Directory to scan for input spreadsheets (`.csv`, `.xlsx`):

  ```bash
  --input-root /data/jobs/123/input
  ```

  → `RunRequest.input_root = Path(...)`

If both `--input` and `--input-root` are provided, the CLI fails fast with a
usage error (mirroring the `RunRequest` invariant).

### 3.2 Sheet filtering (XLSX only)

Optional flags to restrict which sheets are processed:

* `--input-sheet NAME` (repeatable)
  e.g.:

  ```bash
  --input-sheet MemberData \
  --input-sheet Summary
  ```

* or `--input-sheets NAME1,NAME2,...` (if supported by the parser).

These set `RunRequest.input_sheets` to the provided list. CSV inputs ignore
sheet filters (they’re treated as a single implicit sheet).

### 3.3 Output and logs

Where to write normalized workbooks and logs:

* `--output-dir DIR`
  → `RunRequest.output_root = Path(DIR)`

* `--logs-dir DIR`
  → `RunRequest.logs_root = Path(DIR)`

If omitted, the engine may infer sensible defaults from the input location
(e.g. sibling `output/` and `logs/` directories), but backend workers should
**explicitly pass both** to keep job layout predictable.

### 3.4 Config selection

Config package and manifest:

* `--config-package NAME` (optional; default: `ade_config`)

  ```bash
  --config-package ade_config
  ```

  → `RunRequest.config_package = "ade_config"`

* `--manifest-path PATH` (optional)

  ```bash
  --manifest-path /data/config_packages/my-config/manifest.json
  ```

  → `RunRequest.manifest_path = Path(PATH)`

If `--manifest-path` is not provided, the engine resolves `manifest.json`
from the `config_package` using `importlib.resources`.

### 3.5 Execution options

Execution‑time flags that don’t change the core pipeline semantics:

* `--safe-mode`
  → `RunRequest.safe_mode = True`

  A hint that the caller wants a more conservative execution (e.g. disable
  optional integrations or external sinks). OS‑level resource limits are still
  enforced by the worker environment, not by the engine itself.

* `--metadata KEY=VALUE` (repeatable, if supported)
  For injecting simple tags into `RunRequest.metadata`:

  ```bash
  --metadata job_id=abc123 \
  --metadata config_id=config-01
  ```

  The engine treats metadata as opaque; it simply mirrors it into
  `RunContext.metadata`, `artifact.json`, and telemetry envelopes. How those
  keys relate back to “jobs” is entirely a backend concern.

---

## 4. Non‑run commands

The CLI also supports simple non‑run queries:

* `--version`
  Print engine version (and optionally config manifest version if discoverable)
  and exit with code `0`. No pipeline is executed.

* `--manifest-path PATH` without any `--input`/`--input-root`
  Validate/inspect the manifest at `PATH` and exit. Implementation details
  (e.g., printing schema or summary) are intentionally light and can evolve,
  but **no files are processed**.

---

## 5. Output format and exit codes

### 5.1 JSON summary

For a normal run, the CLI prints a single JSON object to stdout. Conceptually:

```jsonc
{
  "engine_version": "0.0.0",
  "run": {
    "run_id": "run-uuid",
    "status": "succeeded",
    "outputs": ["/data/jobs/123/output/normalized.xlsx"],
    "artifact": "/data/jobs/123/logs/artifact.json",
    "events": "/data/jobs/123/logs/events.ndjson",
    "processed_files": ["input.xlsx"],
    "error": null
  }
}
```

Fields mirror `RunResult`:

* `status`: `"succeeded"` or `"failed"`.
* `outputs`: list of output workbook paths (usually 1).
* `artifact`: path to `artifact.json`.
* `events`: path to `events.ndjson`.
* `processed_files`: basenames of input files the engine actually read.
* `error`: `null` on success, or a human‑readable error summary on failure.

The ADE backend should **not parse internal error messages** for control flow;
it should rely on `status` and the presence of the log files. Error messages
are for logs and operator visibility.

### 5.2 Exit codes

* `0`

  * All non‑run commands completed successfully, or
  * Run finished and `status == "succeeded"`.

* Non‑zero

  * CLI usage error (e.g. both `--input` and `--input-root`), or
  * Run failed and `status == "failed"`.

The exact non‑zero values are not intended as a stable API; backend code
should treat any non‑zero as “run/CLI failed” and use the JSON summary +
log files for details.

---

## 6. Integration with ADE backend

### 6.1 Worker lifecycle (typical)

A typical end‑to‑end flow:

1. **API request** arrives:
   “Run config `<config_id>` on uploaded document `<document_id>`.”

2. **Backend resolves job** to a venv and paths:

   * Ensure a venv exists for `<config_id>/<build_id>` with:

     * `ade_engine` installed.
     * the appropriate `ade_config` version installed.
   * Create a job directory:

     ```text
     /data/jobs/<job_id>/
       input/
         input.xlsx
       output/
       logs/
     ```

3. **Backend schedules worker** (thread/process/container) with:

   * venv location,
   * job directory paths,
   * config identifier.

4. **Worker activates venv** and invokes the engine, either:

   * **CLI**:

     ```bash
     /path/to/.venv/<config_id>/<build_id>/bin/python -m ade_engine \
       --input /data/jobs/<job_id>/input/input.xlsx \
       --output-dir /data/jobs/<job_id>/output \
       --logs-dir /data/jobs/<job_id>/logs \
       --config-package ade_config \
       --metadata job_id=<job_id> \
       --metadata config_id=<config_id>
     ```

   * **Python API** (equivalent):

     ```python
     from pathlib import Path
     from ade_engine import run

     result = run(
         config_package="ade_config",
         input_files=[Path(f"/data/jobs/{job_id}/input/input.xlsx")],
         output_root=Path(f"/data/jobs/{job_id}/output"),
         logs_root=Path(f"/data/jobs/{job_id}/logs"),
         metadata={"job_id": job_id, "config_id": config_id},
     )
     ```

5. **Worker updates backend state**:

   * Parse CLI JSON or inspect `RunResult`.
   * Persist:

     * output workbook path(s),
     * `artifact.json` and `events.ndjson` paths,
     * status (`succeeded` / `failed`).
   * Optionally parse `artifact.json` and `events.ndjson` to drive UI and
     reporting.

Importantly, the engine:

* Never needs to know `job_id` or `workspace_id` semantics.
* Treats those values as opaque metadata.

### 6.2 Python API vs CLI

Both are first‑class and interchangeable:

* **CLI**:

  * Natural fit for process‑oriented workers or containerized jobs.
  * Clear separation of concerns: worker = shell command runner.

* **Python API**:

  * Simplifies integration tests and programmatic orchestration.
  * Avoids JSON parsing overhead and stringly‑typed flags.

The core invariant is: **both paths go through the same `Engine.run()` logic**.

---

## 7. Local debugging workflows

### 7.1 CLI from a developer machine

Example:

```bash
python -m ade_engine \
  --input ./examples/input.xlsx \
  --output-dir ./examples/output \
  --logs-dir ./examples/logs
```

Then inspect:

* `examples/output/` — normalized workbook(s).
* `examples/logs/artifact.json` — mapping, validation, and run metadata.
* `examples/logs/events.ndjson` — telemetry stream.

### 7.2 Python from a REPL or test

Example:

```python
from pathlib import Path
from ade_engine import run

result = run(
    input_files=[Path("examples/input.xlsx")],
    output_root=Path("examples/output"),
    logs_root=Path("examples/logs"),
    metadata={"debug": True},
)

print(result.status, result.output_paths)
```

Both workflows use the same engine and produce the same artifact/telemetry
structure; only the calling mechanism differs.

---

## 8. Security and isolation

The CLI assumes:

* It is running in a **config‑scoped venv** whose dependencies are controlled
  by the ADE backend.
* Config code (`ade_config`) may be arbitrary Python.

Backends should:

* Treat workers as the trust boundary.
* Use OS‑level controls (cgroups, sandboxing, network policies, etc.) as
  appropriate for their environment.
* Avoid giving workers broader filesystem/network access than required to
  read inputs and write outputs/logs.

The engine and CLI themselves remain deliberately simple: they operate only on
paths and metadata passed in; all higher‑level security and scheduling policies
live in the ADE API layer.
```

# apps/ade-engine/docs/10-testing-and-quality.md
```markdown
# Testing & Quality

This document describes how we test **`ade_engine`** and what “good” test
coverage means for this project.

It is written for engine maintainers and advanced config authors who need to
understand how the runtime behaves and how to keep changes safe and
predictable over time.

---

## 1. Goals and principles

Our testing strategy is built around a few simple ideas:

- **Deterministic behavior**  
  Given the same `ade_config`, manifest, and input files, the engine should
  produce the **same** normalized workbook, `artifact.json`, and
  `events.ndjson`.

- **Separation of concerns**  
  Each layer should be testable in isolation:
  - IO and table detection,
  - column mapping,
  - normalization and validation,
  - artifact and telemetry,
  - high‑level `Engine.run`.

- **Stable contracts**  
  The shapes and semantics of:
  - `RunRequest` / `RunResult`,
  - `artifact.json`,
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
    test_config_runtime.py
    test_artifact.py
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
* `tests/test_config_runtime.py` → `config_runtime.py`, `schemas/manifest.py`
* `tests/test_artifact.py` → `artifact.py`
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
  * `artifact.json`,
  * `events.ndjson`.

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

This makes it easy for multiple tests to spin up isolated configs with
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

  * Error if both `input_files` and `input_root` are provided.
  * Error if neither is provided.
* `RunPaths` resolution:

  * Correct derivation of `input_root`, `output_root`, and `logs_root` from
    `RunRequest`.
  * Directories are created if missing.
* `Engine.run` happy path:

  * With a mocked `ConfigRuntime` / pipeline, returns `RunResult` with
    expected paths and status.
* `Engine.run` failure path:

  * Inject an exception in the pipeline and ensure:

    * `RunResult.status == "failed"`,
    * `error` is set,
    * `artifact.json` exists and has `run.status == "failed"`.

Tests here should not depend on real `ade_config` packages; use mocks or
minimal in‑memory stubs.

### 4.2 Config runtime (`config_runtime.py`, `schemas/manifest.py`)

Key tests:

* Manifest loading:

  * Loads from `manifest_path` override.
  * Loads from `ade_config/manifest.json` by default.
* Validation via `ManifestV1`:

  * Required fields enforced.
  * Optional fields default correctly.
* `ManifestContext` helpers:

  * `column_order`, `column_meta`, `defaults`, `writer`, `env` behave as
    expected for typical manifests.
* Script discovery:

  * `ColumnModule` import and function discovery from `script` paths.
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

  * Produces `RawTable` with correct header/data ranges given basic
    row detectors.
  * Handles empty sheets or sheets with no detectable table gracefully.

### 4.4 Column mapping (`pipeline/mapping.py`)

Key tests:

* Per‑column scoring:

  * Given controlled detector outputs, verify how scores are aggregated into
    `ColumnMapping`.
* Threshold behavior:

  * Columns below `mapping_score_threshold` are not mapped.
* Tie‑breaking:

  * Ties resolved by `manifest.columns.order`.
* Extra columns:

  * Unmapped columns become `ExtraColumn`s when writer config says so.
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

  * Headers appear in `manifest.columns.order` followed by extras.
  * Data rows written in stable, documented order.
* Per‑table sheet mode (if supported by writer config):

  * Per‑table sheet naming and collision handling.
* Hook integration:

  * `on_before_save` hooks can modify the workbook before save.
* Output paths:

  * Workbook saved to expected location under `output_root`.

### 4.7 Artifact and telemetry (`artifact.py`, `telemetry.py`)

Key tests:

* Artifact lifecycle:

  * `start` → `mark_success` / `mark_failure` → `flush` produce a valid
    `artifact.json`.
* Run section:

  * `run.status` matches the final `RunResult`.
  * `outputs` and `metadata` are propagated correctly.
* Tables section:

  * `mapping`, `unmapped`, and `validation` entries reflect the given
    `RawTable`, `MappedTable`, and `NormalizedTable`.
* Telemetry events:

  * `FileEventSink` writes well‑formed NDJSON.
  * `PipelineLogger.note` and `.event` respect `min_*_level` thresholds.

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
       output_root=tmp_path / "output",
       logs_root=tmp_path / "logs",
       metadata={"test_case": "basic_e2e"},
   )
   ```

5. Assert:

   * `result.status == "succeeded"`.
   * Workbook exists at each `output_paths` entry and is a valid XLSX.
   * `artifact.json` exists and contains:

     * `run.status == "succeeded"`,
     * one or more `tables` entries.
   * `events.ndjson` exists and contains at least `run_started` and
     `run_completed` events.

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

* For selected configs and inputs:

  * Take a **snapshot** of:

    * `artifact.tables[*].mapping`,
    * `artifact.tables[*].unmapped`.
* Add a test that:

  * Runs the engine with the same inputs/config.
  * Compares the new mapping snapshot to the stored one.
  * Fails if fields or scores differ unexpectedly.

When mapping behavior must change intentionally:

* Update the stored snapshot as part of the change.
* Mention the behavior change in the PR description / changelog.

### 6.2 Artifact & telemetry schema contracts

We treat `artifact.json` and `events.ndjson` as external contracts.

Tests should:

* Validate serialized JSON against the Pydantic models (and optional JSON
  Schemas).
* Assert key invariants, for example:

  * `artifact.run.status` always present.
  * `run.outputs` non‑empty on success.
  * Every validation issue has `row_index`, `field`, `code`, `severity`.
  * Every telemetry event envelope has `schema`, `version`, `run_id`,
    `timestamp`, and `event`.

If a breaking change to these shapes is necessary, tests should make the
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

* Use `artifact.json` produced by failing tests:

  * Inspect `tables[*].mapping` for unexpected field/header matches.
  * Inspect `tables[*].validation` for unexpected issues.
* Add temporary assertions or `PipelineLogger.note` calls in the failing area,
  then re‑run the specific test.

### 8.2 Script errors

Typical sources:

* Exceptions inside config detectors, transforms, validators, or hooks.
* Misconfigured manifest `script` paths.

Debugging steps:

1. Reproduce with a focused test using the failing config fixture.
2. Check error details in:

   * `RunResult.error`,
   * `artifact.run.error`,
   * `events.ndjson` (`run_failed` event payload).
3. Add a minimal repro to `tests/test_config_runtime.py` or
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
   * `artifact.json` and `events.ndjson` formats preserved, or versioned
     with explicit tests.

3. **Performance considered**

   * Large‑input tests still pass.
   * No obvious new O(n²) patterns or unbounded structures.

4. **Docs updated**

   * README and relevant docs under `apps/ade-engine/docs/` reflect the new
     behavior.

5. **Config compatibility**

   * Existing configs continue to work, or migration steps are clearly
     documented (including changes to script APIs or manifest schema).

If tests are failing for reasons that look like “expected breakage”, expand
the tests to encode the new behavior, then update snapshots and docs in the
same change.

---

With this testing layer in place, you should be able to evolve the engine
confidently: small unit changes are caught early, and contract tests guard the
interfaces that ADE API, configs, and other systems rely on.
```

# apps/ade-engine/docs/README.md
```markdown
# ADE Engine – Detailed Documentation Index

This folder contains deeper “chapters” that expand on the high-level overview
in `ade_engine/README.md`. Read that first, then use this folder as a reference
while building or extending the engine and configs.

Recommended reading order (mirrors the pipeline flow):

1. [`01-engine-runtime.md`](./01-engine-runtime.md)  
   How the `Engine` is constructed, how `RunRequest` and `RunResult` work, and
   what a single engine run looks like end‑to‑end.

2. [`02-config-and-manifest.md`](./02-config-and-manifest.md)  
   How the engine discovers and uses the `ade_config` package, its
   `manifest.json`, and the Python schema models in `ade_engine.schemas`.

3. [`03-io-and-table-detection.md`](./03-io-and-table-detection.md)  
   How input files are discovered and read, how sheets are selected, and how
   row detectors find table boundaries (`RawTable`).

4. [`04-column-mapping.md`](./04-column-mapping.md)  
   How raw headers/columns are mapped to canonical fields via detectors,
   scoring, and tie‑breaking (`MappedTable`).

5. [`05-normalization-and-validation.md`](./05-normalization-and-validation.md)  
   How transforms and validators run per row to produce normalized data and
   validation issues (`NormalizedTable`).

6. [`06-artifact-json.md`](./06-artifact-json.md)  
   The structure of `artifact.json`, how the artifact is updated during a run,
   and how it is used by ADE API for reporting.

7. [`07-telemetry-events.md`](./07-telemetry-events.md)  
   The telemetry event system, event envelopes, sinks, and the NDJSON log.

8. [`08-hooks-and-extensibility.md`](./08-hooks-and-extensibility.md)  
   Hook stages, how hooks are registered, and patterns for extending behavior
   without modifying the engine.

9. [`09-cli-and-integration.md`](./09-cli-and-integration.md)  
   CLI entrypoint, flags, JSON output, and how the ADE backend calls the
   engine inside virtual environments.

10. [`10-testing-and-quality.md`](./10-testing-and-quality.md)  
    Testing strategy, fixtures, regression checks, and change‑management
    guidelines.

Each document assumes you are familiar with the concepts introduced in
`ade_engine/README.md` and in the preceding chapters.
```

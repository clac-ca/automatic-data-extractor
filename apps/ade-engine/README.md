# ADE Engine (Runtime)

The **ADE engine** is a config‑driven runtime that turns messy spreadsheets into
a **normalized Excel workbook plus a full audit artifact**. You can think of it
as:

> “Run a pipeline over spreadsheets using an `ade_config` plugin that defines
> how to detect, map, transform and validate data.”

This document describes the **architecture**, **folder structure**, **core
types**, and **script APIs** you need to understand to implement or extend the
engine.

---

## Terminology

| Concept            | Term in code      | Notes                                                     |
| ------------------ | ----------------- | --------------------------------------------------------- |
| Run                | `run`             | One call to `Engine.run()` or one CLI invocation          |
| Config package     | `config_package`  | Installed `ade_config` package for this run               |
| Config version     | `manifest.version`| Version declared by the config package manifest           |
| Build              | build             | Virtual environment built for a specific config version   |
| User data file     | `source_file`     | Original spreadsheet on disk                              |
| User sheet         | `source_sheet`    | Worksheet/tab in the spreadsheet                          |
| Canonical column   | `field`           | Defined in manifest; never call this a “column”           |
| Physical column    | column            | B / C / index 0,1,2… in a sheet                           |
| Output workbook    | normalized workbook| Written to `output_dir`; includes mapped + normalized data|

Use these names everywhere in code comments, telemetry, docs, and filenames.
Avoid synonyms like “input file” (use **source file**), “output file” (say
**output workbook** or explicitly refer to artifact/events), or mixing “field”
and “column”. Backend notions like run request/workspace/tenant remain outside the
engine and only show up as opaque metadata if the caller passes them.

---

## 1. Big picture

At runtime, inside a **pre‑built virtual environment**:

1. The engine loads a versioned **config package** (`ade_config`) with:
   - a JSON/YAML **manifest** (fields, writer settings, hooks)
   - **row detectors** (table finding)
   - **column detectors** (field recognition)
   - **transforms** & **validators**
   - **hooks** (lifecycle callbacks)
2. It **reads source spreadsheets** (CSV/XLSX) in streaming mode.
3. It **detects tables**, **maps columns** to canonical fields, and
   **normalizes** values row‑by‑row using the config code.
4. It emits:
   - a normalized **`output.xlsx`** workbook
   - an **`artifact.json`** (human/audit readable)
   - an **`events.ndjson`** telemetry stream.

The engine itself is **business‑logic free**: all domain rules live in `ade_config`.

In production, the ADE API:

- builds a **frozen venv** per config (`ade_engine` + a specific `ade_config` version),
- then, for each **run request**, launches a worker (process or thread) inside that venv,
- and calls the engine with **file paths** (source / output / logs).

From the engine’s perspective, it just runs synchronously inside an isolated environment
with `ade_config` installed; **it is run-scoped only—run IDs and workspace concepts belong to the backend**.

---

### Excel support (openpyxl)

The engine uses **openpyxl** for Excel IO:

- **Supported formats** — Excel Open XML only: `xlsx`, `xlsm`, `xltx`, `xltm`. Older `xls` is not supported and is rejected.
- **Source files are read‑only** — workbooks are opened with `read_only=True` and never saved back; the engine always writes a new normalized workbook.
- **Performance posture** — openpyxl in normal mode can use significant memory (docs note ~50× file size). The engine reads in streaming mode and keeps writes simple, but very large outputs still consume RAM proportionally.

CSV uses Python’s CSV reader; only Excel IO goes through openpyxl.

---

### 1.1 Runtime & virtual environments

The deployment model is:

- **Build time (outside the engine)**  
  - ADE backend creates a venv for `<config_id>/<build_id>`.
  - Installs `ade_engine` and the selected `ade_config`.
  - Optionally pins dependencies and writes a `packages.txt` for reproducibility.

- **Run time (inside the venv)**  
  - Backend dispatches a run to a worker (thread/process/container).  
  - Worker activates that venv and invokes the engine with explicit paths:

    ```bash
    # Typical worker invocation from the ADE API (one run, often dispatched from a backend run queue)
    /path/to/.venv/<config_id>/<build_id>/bin/python \
      -m ade_engine \
      --input /data/runs/<run_id>/input/input.xlsx \
      --output-dir /data/runs/<run_id>/output \
      --logs-dir /data/runs/<run_id>/logs
    ```

  - The engine:
    - reads the source file(s) (e.g., `input.xlsx`),
    - imports `ade_config` and reads its `manifest.json`,
    - runs the pipeline once for that call,
    - writes the normalized workbook (e.g., `normalized.xlsx`), `artifact.json`, `events.ndjson` to the given output/logs dirs.

The **engine does not know or care about backend run IDs**. It only needs:

- the config to use (`config_package`, `manifest_path`),
- one or more **source files**,
- where to write the output workbook(s) and logs.

The ADE API is responsible for mapping those paths back to any run record in its own database.

The engine has **no knowledge** of:

- the ADE API,
- workspaces, config package registry, or queues,
- backend run requests or their IDs,
- how many threads/processes are running.

It is a pure “source files → normalized workbook + logs” component. The backend may choose to associate one backend run request with one or many runs; that mapping stays outside the engine.

---

## 2. Package layout (layered and obvious)

Make the layering explicit with clear subpackages:

```text
ade_engine/
  core/                      # Runtime orchestrator + pipeline
    __init__.py              # Re-export Engine, RunRequest, RunResult, etc.
    engine.py                # Engine.run orchestration
    types.py                 # RunRequest, RunResult, RunContext, RawTable, enums (core runtime models)
    pipeline/
      __init__.py            # Re-export execute_pipeline(), RunPhase helpers
      extract.py
      mapping.py
      normalize.py
      write.py
      pipeline_runner.py     # Pipeline orchestrator (execute_pipeline)

  config/                    # Config loading and registries (renamed from config_runtime)
    __init__.py
    loader.py                # load_config_runtime
    manifest_context.py
    column_registry.py
    hook_registry.py

  infra/                     # IO + artifact + telemetry plumbing
    io.py
    artifact.py
    telemetry.py

  schemas/                   # Python-first schemas (Pydantic)
    __init__.py
    manifest.py
    telemetry.py
    artifact.py

  cli/                 # Typer-based CLI (`ade-engine`) with subcommands
    __init__.py
    app.py             # Typer app wiring
    commands/          # One file per command for maintainability
      run.py           # primary run command
      version.py       # prints version
  __main__.py          # `python -m ade_engine` → cli.app()

# Public API surface (top-level imports from ade_engine/__init__.py)
from ade_engine.core.engine import Engine
from ade_engine.core.types import RunRequest, RunResult, EngineInfo, RunStatus
from ade_engine import __version__

def run(*args, **kwargs) -> RunResult:
    """Convenience helper: Engine().run(...)"""
    engine = Engine()
    return engine.run(*args, **kwargs)

__all__ = [
    "Engine",
    "run",
    "RunRequest",
    "RunResult",
    "EngineInfo",
    "RunStatus",
    "__version__",
]
```

Layering rules:

- Runtime/core depends on config types and infra helpers.
- `config/` (formerly `config_runtime/`) can depend on schemas and infra where needed.
- `infra/` holds IO + artifact/telemetry plumbing used by both core and config.
- `cli/` is a thin wrapper over the public API; keep business logic in `core/`.
- Hooks remain part of the core extension model via `config/hook_registry.py` (legacy path: `config_runtime/hook_registry.py`); hook invocation helpers can live in `core/` if desired.

If you know this layout, you know where everything lives:

- **How do I run the engine?** → `core/engine.py`, `ade_engine/__init__.py`
- **How do we load config scripts?** → `config/loader.py` (legacy path: `config_runtime/loader.py`)
- **How does the pipeline work?** → `core/pipeline/`
- **Where is artifact/telemetry written?** → `infra/artifact.py`, `infra/telemetry.py`

### 2.1 Public API (top-level `ade_engine`)

Keep the public surface obvious and small at the package root:

```python
# ade_engine/__init__.py
from ade_engine.core.engine import Engine
from ade_engine.core.types import RunRequest, RunResult, EngineInfo, RunStatus
from ade_engine import __version__  # however versioning is managed


def run(*args, **kwargs) -> RunResult:
    """Convenience helper: Engine().run(...)"""
    engine = Engine()
    return engine.run(*args, **kwargs)


__all__ = [
    "Engine",
    "run",
    "RunRequest",
    "RunResult",
    "EngineInfo",
    "RunStatus",
    "__version__",
]
```

Usage stays simple (one source file, explicit destinations):

```python
from pathlib import Path
from ade_engine import Engine, run, RunRequest

result = run(
    RunRequest(
        input_files=[Path("input.xlsx")],
        output_dir=Path("output"),
        logs_dir=Path("logs"),
    )
)
```

You only need to dig into `pipeline`, `artifact`, or `telemetry` if you are working on the engine internals.
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
from enum import Enum
from typing import Any, Literal, Mapping, Sequence

class RunStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class RunErrorCode(str, Enum):
    CONFIG_ERROR = "config_error"
    INPUT_ERROR = "input_error"
    HOOK_ERROR = "hook_error"
    PIPELINE_ERROR = "pipeline_error"
    UNKNOWN_ERROR = "unknown_error"

class RunPhase(str, Enum):
    INITIALIZATION = "initialization"
    LOAD_CONFIG = "load_config"
    EXTRACTING = "extracting"
    MAPPING = "mapping"
    NORMALIZING = "normalizing"
    WRITING_OUTPUT = "writing_output"
    HOOKS = "hooks"
    COMPLETED = "completed"
    FAILED = "failed"
```

**EngineInfo** (thin metadata for CLI/telemetry)

```python
@dataclass(frozen=True)
class EngineInfo:
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

    # Source selection (one of the two is required; providing both is an error)
    input_files: Sequence[Path] | None = None  # preferred: explicit source files, typically [Path("input.xlsx")]
    input_dir: Path | None = None              # optional: scan folder for CSV/XLSX

    # Optional sheet filtering (XLSX only; CSV has a single implicit sheet)
    input_sheets: Sequence[str] | None = None  # restrict to specific sheet names

    # Output / logs
    output_dir: Path | None = None            # folder for normalized output workbook(s)
    logs_dir: Path | None = None              # folder for artifact.json + events.ndjson

    # Metadata (telemetry-only correlation tags)
    metadata: Mapping[str, Any] | None = None
```

The engine requires **exactly one** of `input_files` or `input_dir`. If both are provided,
it fails fast with a `ValueError` rather than guessing.

Safe mode (e.g., `ADE_SAFE_MODE=1`) is handled by the outer app: it may choose not to import `ade_config` or invoke the engine. There is no run-level `safe_mode` flag in `RunRequest`.

In the simplest case, the ADE API:

* resolves the run’s primary **source file** (often inside a backend run folder, e.g. `/data/runs/<run_id>/input/input.xlsx`),
* chooses output/logs dirs (e.g. `/data/runs/<run_id>/output` and `/data/runs/<run_id>/logs`),
* and calls:

```python
RunRequest(
    config_package="ade_config",
    input_files=[Path("/data/runs/<run_id>/input/input.xlsx")],
    output_dir=Path("/data/runs/<run_id>/output"),
    logs_dir=Path("/data/runs/<run_id>/logs"),
    metadata={"run_id": "<run_id>", "config_id": "<config_id>"},
)
```

The engine doesn’t know what `run_id` means; if provided, metadata is treated as opaque and only echoed in telemetry for correlation.

**RunError** and **RunResult**

Structured error info plus the overall outcome:

```python
@dataclass(frozen=True)
class RunError:
    code: RunErrorCode
    stage: RunPhase | None
    message: str

@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    error: RunError | None
    run_id: str
    output_paths: tuple[Path, ...]      # normalized output workbooks (usually length 1)
    artifact_path: Path                 # audit JSON
    events_path: Path                   # telemetry NDJSON
    processed_files: tuple[str, ...]    # source file names as seen by the engine
```

**RunPaths**

Resolved filesystem layout for a run:

```python
@dataclass(frozen=True)
class RunPaths:
    input_dir: Path
    output_dir: Path
    logs_dir: Path
    artifact_path: Path       # logs_dir / "artifact.json"
    events_path: Path         # logs_dir / "events.ndjson"
```

* If you pass `output_dir`/`logs_dir`, those are used directly.
* If you only pass `input_files`, the engine infers defaults (e.g. sibling `output` / `logs`
  folders next to the first source file).
* If you only pass `input_dir`, the engine infers defaults relative to that directory
  (e.g. `input_dir.parent / "output"` and `input_dir.parent / "logs"`).
* It is an error to provide both `input_files` and `input_dir`.
* CLI flags map directly: `--output-dir` → `RunPaths.output_dir`, `--logs-dir` → `RunPaths.logs_dir`, `--input-dir` → `RunRequest.input_dir`.

**RunContext**

Internal context shared across pipeline, hooks, and telemetry:

```python
@dataclass
class RunContext:
    run_id: str                 # generated UUID or similar per run
    metadata: dict[str, Any]    # optional caller-supplied metadata (used for telemetry correlation only)
    manifest: ManifestContext   # see config/manifest_context.py (legacy path: config_runtime/manifest_context.py)
    paths: RunPaths
    started_at: datetime
    state: dict[str, Any] = field(default_factory=dict)  # per-run scratch space for scripts (not shared across runs/threads)
```

`RunContext.state` is **per run**: each call to `Engine.run()` gets a fresh
dict that detectors, transforms, validators, and hooks can share during that
run. It is never shared across runs or threads. A single `Engine.run` executes
sequentially in one thread/process; any concurrency is implemented by the ADE
API running multiple workers, each with its own `RunContext`.

Exception classes are aligned with `RunErrorCode`:

### 3.3 Errors (`errors.py`)

```python
class AdeEngineError(Exception): ...
class ConfigError(AdeEngineError): ...      # → RunErrorCode.CONFIG_ERROR
class InputError(AdeEngineError): ...       # → RunErrorCode.INPUT_ERROR
class HookError(AdeEngineError): ...        # → RunErrorCode.HOOK_ERROR
class PipelineError(AdeEngineError): ...    # → RunErrorCode.PIPELINE_ERROR
```

Guidelines:

- Config loading raises `ConfigError` for manifest/schema/script issues.
- IO/missing sheets/unsupported formats raise `InputError`.
- Hook failures surface as `HookError`.
- Unexpected pipeline bugs raise `PipelineError`.

`Engine.run` maps these to `RunError.code` in one place (e.g.,
`_error_to_run_error(exc, stage)`) so `RunResult`, artifact, and telemetry all
share the same `code`/`message`/`stage`.

The ADE backend may include a `run_request_id` inside `metadata`, but the engine just
treats it as opaque metadata. The engine is always run-scoped; any run request/run
mapping is a backend concern.

Because all per‑run state lives on `RunContext` and not on the `Engine` instance
itself, the `Engine` class is **logically stateless** and can be safely reused
across requests or threads (as long as each call uses a fresh `RunRequest`).

### 3.2 Table and pipeline types

These types model tables and mapping/normalization results.

```python
@dataclass
class RawTable:
    source_file: Path
    source_sheet: str | None
    table_index: int              # 0-based ordinal within the sheet (supports multiple tables per sheet)
    header_row: list[str]
    data_rows: list[list[Any]]
    header_row_index: int         # 1-based row index in original sheet
    first_data_row_index: int     # 1-based
    last_data_row_index: int      # 1-based
```

Column mapping:

```python
@dataclass
class ScoreContribution:
    field: str                # canonical field
    detector: str             # "module.func"
    delta: float

@dataclass
class MappedColumn:
    field: str                # canonical field name
    header: str               # original header text
    source_column_index: int  # 0-based input column index (converted from 1-based script inputs)
    score: float
    contributions: tuple[ScoreContribution, ...]
```

Unmapped columns:

```python
@dataclass
class UnmappedColumn:
    header: str
    source_column_index: int   # 0-based input column index
    output_header: str         # "raw_<safe_name>"
```

Mapped and normalized tables:

```python
@dataclass
class ColumnMap:
    mapped_columns: list[MappedColumn]
    unmapped_columns: list[UnmappedColumn]

@dataclass
class MappedTable:
    raw: RawTable
    column_map: ColumnMap

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
    rows: list[list[Any]]            # rows in manifest.order + unmapped columns (if appended)
    validation_issues: list[ValidationIssue]
    output_sheet_name: str
```

`RunPhase` is used consistently for pipeline transitions, telemetry, and `RunError.stage`. Enum `.value` strings are snake_case (`"initialization"`, `"load_config"`, `"extracting"`, `"mapping"`, `"normalizing"`, `"writing_output"`, `"hooks"`, `"completed"`, `"failed"`) and used in telemetry `pipeline_transition` events.

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
3. Uses helper methods on `ManifestContext` for convenient access (column order, column meta, defaults, writer config).

For **external validation or documentation**, the engine can emit JSON Schema via
`ManifestV1.model_json_schema()` into a generated file (e.g. `manifest_v1.schema.json`),
but that JSON is derived from the Python models, not hand-maintained.

Conceptually the manifest looks like:

```jsonc
{
  "schema": "ade.manifest/v1",
  "version": "1.2.3",
  "name": "My Config",
  "description": "Optional",
  "script_api_version": 1,

  "columns": {
    "order": ["member_id","email","..."],
    "fields": {
      "member_id": {
        "label": "Member ID",
        "module": "column_detectors.member_id",
        "required": true,
        "synonyms": ["member id", "member#"],
        "type": "string"
      },
      "email": {
        "label": "Email",
        "module": "column_detectors.email",
        "required": true,
        "type": "string"
      }
    }
  },
  "hooks": {
    "on_run_start": ["hooks.on_run_start"],
    "on_after_extract": ["hooks.on_after_extract"],
    "on_after_mapping": ["hooks.on_after_mapping"],
    "on_before_save": ["hooks.on_before_save"],
    "on_run_end": ["hooks.on_run_end"]
  },
  "writer": {
    "append_unmapped_columns": true,
    "unmapped_prefix": "raw_",
    "output_sheet": "Normalized"
  }
}
```

Key ideas:

- **Top-level fields** describe the config and script API version.
- Use the word **field** for manifest entries; use **column** only for physical spreadsheet columns. `columns.order` is the list of field IDs; `columns.fields` maps those IDs to `FieldConfig` objects.
- Module paths are relative to `ade_config` and start with `column_detectors.<field_name>` or `hooks.<hook_name>`.
- `script_api_version` is the only script contract version identifier; do not call it “API version” or “manifest API version”.

`config/manifest_context.py` (legacy path: `config_runtime/manifest_context.py`) turns this into a typed `ManifestContext` with helpers:
`columns.order`, `columns.fields`, and `writer` (engine-level defaults like timeouts or thresholds are fixed in code for manifest v1).

---

## 5. How the engine runs

### 5.1 Public API (`__init__.py` + `engine.py`)

The main entry points:

```python
from pathlib import Path
from ade_engine import Engine, run, RunRequest

# Simple: one source file, explicit output/logs
engine = Engine()
result = engine.run(
    RunRequest(
        input_files=[Path("input.xlsx")],
        output_dir=Path("output"),
        logs_dir=Path("logs"),
    )
)

# Convenience helper: sugar over Engine.run
result = run(
    input_files=[Path("input.xlsx")],
    output_dir=Path("output"),
    logs_dir=Path("logs"),
)
```

`Engine` is **logically stateless**: it does not keep any mutable per‑run data on the instance.
Each call to `run()` constructs a fresh `RunContext` and `state` dict. You can safely reuse a
single `Engine` across threads or requests as long as each call uses its own `RunRequest`.

Under the hood, `Engine.run()`:

1. Normalizes a `RunRequest` into `RunPaths` and `RunContext`:

   * chooses `input_dir` (from source files or explicit folder),
   * chooses `output_dir` and `logs_dir` (from request or defaults based on source location),
   * generates a `run_id`,
   * seeds `metadata` and a shared `state` dict.
2. Calls `config.loader.load_config_runtime()` (legacy import path: `config_runtime.loader`) to load the manifest, column detectors, row detectors, and hooks.
3. Binds telemetry sinks (`TelemetryConfig.bind`) and creates a `PipelineLogger`.
4. Calls `ON_RUN_START` hooks.
5. Calls `execute_pipeline()` in `pipeline/pipeline_runner.py`:

   * `extract_tables` → `RawTable[]`
   * `map_table` per table → `MappedTable`
   * `normalize_table` per table → `NormalizedTable`
   * `write_workbook` → `output.xlsx`
6. Marks the artifact as success/failure and calls `ON_RUN_END` hooks.
7. Returns a `RunResult`.

The engine is single‑run and synchronous: **one call → one pipeline run**. Concurrency
across runs is handled by the ADE API / worker framework, which:

* looks up the backend record (run request/task/request) associated with the run,
* resolves source/output/log paths,
* then calls `Engine.run()` (or the CLI) in the appropriate venv.

### 5.2 How the ADE backend typically uses the engine

A typical integration in the ADE backend looks like:

1. Request comes in: “run config `<config_id>` on uploaded file `<document_id>`”.

2. Backend:

   * ensures a venv exists for `<config_id>/<build_id>` with `ade_engine` + `ade_config` installed,
   * resolves the document path and creates a per-run working folder (under the backend runs directory) with `input/`, `output/`, `logs/`.

3. Backend enqueues a worker task that:

   * activates the config-specific venv,
   * invokes the engine via CLI or API:

     ```python
     from ade_engine import run

     result = run(
         config_package="ade_config",
        input_files=[Path(f"/data/runs/{run_id}/input/input.xlsx")],
        output_dir=Path(f"/data/runs/{run_id}/output"),
        logs_dir=Path(f"/data/runs/{run_id}/logs"),
        metadata={"run_id": run_id, "config_id": config_id},
     )
     ```

4. Backend stores `RunResult` info and/or parses `artifact.json` and `events.ndjson`
   to update backend run status, reports, etc.

The engine has **no idea** that a backend run record exists; it only sees file paths and metadata.

---

## 6. Pipeline stages (`pipeline/`)

### 6.1 `extract.py` – find tables from raw sheets

Responsible for:

* Listing source files (`io.list_input_files`) if `input_dir` is used,
* Or using the explicit `input_files` provided.
* For each CSV/XLSX:

  * Iterate rows using `io.iter_sheet_rows`
  * Run row detectors (if configured) to score header/data rows
  * Decide table boundaries (header row, first/last data row), continuing to scan for additional tables lower in the sheet
  * Materialize `RawTable` objects (multiple per sheet supported via `table_index`)

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

     * `run`, `state`, `field_name`, `field_config`, `header`,
       `column_values_sample`, `column_values`, `table`, `column_index`,
       `manifest`, `logger`
3. Aggregate scores per field and record `ScoreContribution`s.
4. Pick the best field above the engine’s mapping score threshold (fixed for manifest v1).
5. If no match and `append_unmapped_columns` is true, create `UnmappedColumn`.

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
passing the list of `MappedTable` objects. This is the ideal place for configurations to:

* tweak or correct mappings,
* reorder or drop fields,
* adjust unmapped columns (e.g., rename or drop),

before normalization begins.

### 6.3 `normalize.py` – transforms & validators

For each `MappedTable`:

1. Build a `canonical_row` dict for each raw row, keyed by field.

2. Run `transform` for each field module (if present):

   ```python
def transform(
    *,
    run: RunContext,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,                        # canonical row dict (field -> value)
    field_config: dict | None,        # manifest.columns.fields.get(field_name)
    manifest: ManifestContext,
    logger: PipelineLogger,
    **_,
) -> dict | None:
    ...
   ```

3. Run `validate` for each field module (if present):

   ```python
def validate(
    *,
    run: RunContext,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_config: dict | None,        # manifest.columns.fields.get(field_name)
    manifest: ManifestContext,
    logger: PipelineLogger,
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
  by source file name, then by sheet order within that file, then by table
  detection order.

* Build header rows from `manifest.columns.order` and column labels.

* Append normalized rows (canonical fields + extra columns).

* Invoke `on_before_save` hook (if configured) with the openpyxl `Workbook`.

* Save workbook to a temp path, then atomically move to `output_dir/normalized.xlsx`.

API:

```python
def write_workbook(
    ctx: RunContext,
    cfg: ConfigRuntime,
    tables: list[NormalizedTable],
) -> Path:
    ...
```

### 6.5 `pipeline_runner.py` – orchestrate phases

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

* run info (ID, status, timestamps, outputs)
* config info (schema, version)
* tables (input metadata, table_index for multiple tables per sheet, mapping, validation issues)
* notes (high‑level narrative and hook‑written notes)

Boundaries:

* Artifact stays compact and human-friendly: run-level info, compact mapping summaries (with per-column contributions), compact validation summaries, high-level notes.
* Telemetry (`events.ndjson`) carries per-row or debug-level detail; avoid stuffing raw detector scores for every row/column into `artifact.json`.

`FileArtifactSink` implements:

```python
class FileArtifactSink(ArtifactSink):
   def start(self, *, run: RunContext, manifest: ManifestContext): ...
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
  "version": "1.0.0",
  "run": {
    "id": "run-uuid",
    "status": "succeeded",
    "started_at": "2024-01-01T12:00:00Z",
    "completed_at": "2024-01-01T12:00:05Z",
    "outputs": [".../normalized.xlsx"],
    "engine_version": "0.2.0"
  },
  "config": {
    "schema": "ade.manifest/v1",
    "version": "1.2.3",
    "name": "My Config"
  },
  "tables": [
    {
      "source_file": "input.xlsx",
      "source_sheet": "Sheet1",
      "table_index": 0,
      "header": {
        "row_index": 5,
        "cells": ["ID","Email", "..."]
      },
      "mapped_columns": [
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
      "unmapped_columns": [
        {
          "header": "Notes",
          "source_column_index": 5,
          "output_header": "raw_notes"
        }
      ],
      "validation_issues": [
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
(often in a per‑run logs folder living under a backend run request directory),
the ADE API can safely run many runs in parallel across backend run requests without the engine
needing any shared global state.

Opaque metadata passed via `RunRequest.metadata` is **only** echoed in telemetry envelopes for correlation; it is not stored in `artifact.json`.

### 7.2 Telemetry (`telemetry.py`)

Telemetry events are written as **newline‑delimited JSON** to `events.ndjson` and
are intended to be streamed live by the ADE API (tail + forward) while a run is
executing. This is the engine’s timeline: **artifact.json** is the final audit,
**events.ndjson** is “how we got there”.

Internally they are modeled as Pydantic classes in
`ade_engine.schemas.telemetry` (`TelemetryEnvelope`, `TelemetryEvent`). Those
Python models can also emit a JSON Schema for external consumers. The ADE API
does not rewrite them; it forwards the envelopes verbatim alongside its own
`run.*` wrapper events.

The envelope roughly looks like:

```jsonc
{
  "schema": "ade.telemetry/run-event.v1",
  "version": "1.0.0",
  "run_id": "run-uuid-or-correlation-id",
  "timestamp": "2024-01-01T12:34:56Z",
  "metadata": {
    "run_request_id": "optional-run request-id-from-backend",
    "config_id": "config-abc",
    "workspace_id": "ws-123"
  },
  "event": {
    "event": "run_started",
    "level": "info",
    "payload": {
      "files": 1
    }
  }
}
```

**How it is produced and consumed**

* `PipelineLogger` is the single touchpoint inside the engine. It writes to the
  artifact and, when an event sink is present, appends telemetry envelopes to
  `events.ndjson`.
* The ADE API tails `events.ndjson` in near real‑time (200 ms poll) while the
  process runs and forwards each envelope to clients. Stdout lines are forwarded
  separately as `run.log` events from the API.
* Builds do **not** emit engine telemetry; build streaming is generated by the
  API layer only.

**Canonical event names (current engine emission)**

- `run_started`
- `run_completed`
- `run_failed`
- `pipeline_transition` (phase changes; uses `RunPhase.value`)
- `note` (matches artifact notes)
- `table_completed` (one per table; includes sheet/table indexes and issue counts)

`PipelineLogger` is the only thing pipeline code touches:

```python
logger.note("Run started", level="info", extra="...")
logger.transition("extracting", file_count=3)
logger.event("custom_metric", level="info", rows=100)
logger.record_table({...})   # artifact
```

The ADE API can:

* read `events.ndjson` (or stream it live) to drive UIs / reporting, or
* plug in additional event sinks (e.g., send to a message bus) via `TelemetryConfig`.

**Example combined stream (what clients see)**

When streamed through the ADE API, clients receive both API wrapper events and
engine telemetry:

```
{"object":"ade.run.event","type":"run.created","run_id":"run_01","created":1717002000,"status":"queued","configuration_id":"cfg_123"}
{"object":"ade.run.event","type":"run.started","run_id":"run_01","created":1717002001}
{"object":"ade.run.event","type":"run.log","run_id":"run_01","created":1717002002,"stream":"stdout","message":"mode: normal"}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run_01","timestamp":"2024-05-29T12:00:03Z","metadata":{"workspace_id":"ws_1","configuration_id":"cfg_123"},"event":{"event":"pipeline_transition","level":"info","payload":{"phase":"extracting"}}}
{"schema":"ade.telemetry/run-event.v1","version":"1.0.0","run_id":"run_01","timestamp":"2024-05-29T12:00:08Z","metadata":{"workspace_id":"ws_1","configuration_id":"cfg_123"},"event":{"event":"table_completed","level":"info","payload":{"source_file":"/data/runs/.../input.xlsx","source_sheet":"Sheet1","table_index":0,"validation_issue_count":1}}}
{"object":"ade.run.event","type":"run.completed","run_id":"run_01","created":1717002011,"status":"succeeded","exit_code":0,"error_message":null,"artifact_path":"logs/artifact.json","events_path":"logs/events.ndjson","output_paths":["output/output.xlsx"],"processed_files":["input/input.xlsx"]}
```

If you add new telemetry events, keep the envelope shape stable, add fields
additively, and document the event names here.

---

## 8. Script API overview (config side)

All script entrypoints are **keyword‑only**, should include `**_` for forward
compatibility, and receive `RunContext` as `run` plus a **per-run `state` dict**.
Detector functions must be named `detect_*` so they are easy to discover.

### 8.1 Row detectors (`ade_config.row_detectors.*`)

```python
def detect_*(
    *,
    run: RunContext,           # RunContext (read-only from config’s perspective)
    state: dict,
    row_index: int,            # 1-based index in the sheet
    row_values: list,          # raw cell values for this row
    manifest: ManifestContext,
    logger: PipelineLogger,
    **_,
) -> dict:
    return {"scores": {"header": 0.7}}   # or {"scores": {"data": 0.4}}
```

* Detectors return score dicts; the engine aggregates them.
* `state` exists per run only; never persist data across runs here.

### 8.2 Column detectors (`ade_config.column_detectors.<field>`)

```python
def detect_*(
    *,
    run: RunContext,
    state: dict,
    field_name: str,
    field_config: dict,           # manifest.columns.fields[field_name]
    header: str | None,           # normalized header text
    column_values_sample: list,
    column_values: tuple,
    table: RawTable,              # detected table
    column_index: int,            # 1-based for scripts; engine converts to 0-based internally
    manifest: ManifestContext,
    logger: PipelineLogger,
    **_,
) -> dict:
    return {"scores": {field_name: 0.8}}
```

* Module paths are relative to `ade_config` and start with
  `column_detectors.<field_name>`.
* “Column map” refers to the `MappedTable.column_map` object (mapped + unmapped
  columns); avoid floating the name “ColumnMap” if no type exists in code.

### 8.3 Transforms

```python
def transform(
    *,
    run: RunContext,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,                        # canonical row dict (field -> value)
    field_config: dict | None,        # manifest.columns.fields.get(field_name)
    manifest: ManifestContext,
    logger: PipelineLogger,
    **_,
) -> dict | None:
    # Update row and/or return additional field mappings
    ...
```

Transforms see the latest canonical row state (after mapping). Use `state` for
per-run caches or counters, not for cross-run persistence.

### 8.4 Validators

```python
def validate(
    *,
    run: RunContext,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_config: dict | None,        # manifest.columns.fields.get(field_name)
    manifest: ManifestContext,
    logger: PipelineLogger,
    **_,
) -> list[dict]:
    # Return issue dicts: {"code": "invalid_format", "severity": "error", ...}
    ...
```

Validators must return structured issue dicts; the engine wraps them as
`ValidationIssue` objects.

### 8.5 Hooks (`ade_config.hooks.*`)

Hook stages are fixed and aligned to manifest keys:

```python
class HookStage(str, Enum):
    ON_RUN_START = "on_run_start"
    ON_AFTER_EXTRACT = "on_after_extract"
    ON_AFTER_MAPPING = "on_after_mapping"
    ON_BEFORE_SAVE = "on_before_save"
    ON_RUN_END = "on_run_end"
```

Hook context fields are consistent across stages:

```python
from ade_engine.core.types import RunResult, RunContext
from ade_engine.config.hook_registry import HookContext, HookStage  # legacy path: ade_engine.config_runtime.hook_registry
from ade_engine.core.pipeline import RawTable, MappedTable, NormalizedTable
from ade_engine.infra.artifact import ArtifactSink
from ade_engine.infra.telemetry import EventSink, PipelineLogger
from openpyxl import Workbook
from typing import Any

@dataclass
class HookContext:
    run: RunContext
    state: dict[str, Any]
    manifest: ManifestContext
    artifact: ArtifactSink
    events: EventSink | None
    tables: list[RawTable | MappedTable | NormalizedTable] | None
    workbook: Workbook | None
    result: RunResult | None
    logger: PipelineLogger
    stage: HookStage

def run(context: HookContext) -> None:
    context.logger.note("Run started", stage=context.stage.value)
```

Stages:

* `on_run_start` – before any IO or detection work
* `on_after_extract` – after `RawTable[]` has been built
* `on_after_mapping` – after `MappedTable[]` has been built (ideal for adjusting mappings)
* `on_before_save` – with the finalized `Workbook` and `NormalizedTable[]`
* `on_run_end` – after the run finishes (success or failure), with the `RunResult`

---

### 9. CLI flag → RunRequest mapping

Use consistent mappings between CLI flags and `RunRequest` fields:

| CLI flag        | RunRequest field  |
|-----------------|-------------------|
| `--input`       | `input_files`     |
| `--input-dir`   | `input_dir`       |
| `--input-sheet` | `input_sheets`    |
| `--output-dir`  | `output_dir`      |
| `--logs-dir`    | `logs_dir`        |
| `--config-package` | `config_package` |
| `--manifest-path`  | `manifest_path`  |

Docs and help text should phrase mappings explicitly, e.g., “`--output-dir` → `RunRequest.output_dir`”.

## 9. CLI usage

`ade_engine/cli` provides a Typer-based `ade-engine` command; `__main__.py` forwards to `cli.app()`.

Examples (all run inside the appropriate venv):

```bash
# Print engine version
ade-engine version

# Print engine version + manifest from a path (no run)
ade-engine run --manifest-path ./config/manifest.json --input ./input.xlsx --output-dir ./output --logs-dir ./logs --dry-run

# Run the engine on a single file (typical worker call, paths chosen by backend)
ade-engine run \
  --input ./data/runs/<run_id>/input/input.xlsx \
  --output-dir ./data/runs/<run_id>/output \
  --logs-dir ./data/runs/<run_id>/logs \
  --config-package ade_config \
  --manifest-path ./data/config_packages/my-config/manifest.json
```

The CLI prints a JSON summary mirroring `RunResult`:

```jsonc
{
  "engine_version": "0.2.0",
  "run": {
    "id": "run-uuid",
    "status": "succeeded",
    "output_paths": ["/.../normalized.xlsx"],
    "artifact_path": "/.../logs/artifact.json",
    "events_path": "/.../logs/events.ndjson",
    "processed_files": ["input.xlsx"],
    "error": null
  }
}
```

The ADE backend uses this pattern to run asynchronously: the API enqueues a run request or task,
a worker process/thread in the correct venv executes the CLI for a single run,
the engine does its work and writes outputs/logs, and the API reads
`artifact.json`/`events.ndjson` to drive UIs and reports.

---

## 10. Design principles

This architecture is intentionally:

* **Config‑centric** – ADE engine is a generic spreadsheet pipeline,
  driven entirely by `ade_config` (manifest + scripts).
* **Path‑based, run‑scoped** – the engine deals in **files and folders** only.
  Higher‑level orchestration (run requests, queues, retries) lives in the ADE API.
* **Predictable** – All public entry points and file names follow standard patterns:

  * `Engine.run`, `RunRequest`/`RunResult`
  * `execute_pipeline()`, `extract.py`, `mapping.py`, `normalize.py`, `write.py`
  * `infra/io.py`, `config/loader.py`, `config/hook_registry.py` (legacy: `config_runtime/*`), `infra/artifact.py`, `infra/telemetry.py`
* **Python‑first schemas** – Manifest and telemetry schemas are defined as Python models
  (Pydantic), with JSON Schemas generated as artifacts when needed. See
  `docs/11-ade-event-model.md` for the unified ADE event envelope and streaming
  model shared with the backend.
* **Auditable** – Every detector score, transform, and validation issue can be
  explained via `artifact.json` and `events.ndjson`.
* **Isolated & composable** – Each config build gets its own venv; each engine call runs
  inside that venv, so changes to one config or environment never leak into others.
* **Extensible** – Hooks, telemetry sinks, and script API support evolving needs
  without changing the engine’s core.

With this README and the folder layout above, you should be able to reason about
the engine from scratch and confidently implement or refactor any part of it.

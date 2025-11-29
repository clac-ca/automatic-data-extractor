# ADE Engine (Runtime)

The **ADE engine** is a config‑driven runtime that turns messy spreadsheets into
a **normalized Excel workbook plus telemetry**. You can think of it as:

> “Run a pipeline over spreadsheets using an `ade_config` plugin that defines
> how to detect, map, transform and validate data.”

This document describes the **architecture**, **folder structure**, **core
types**, and **script APIs** you need to understand to implement or extend the
engine.

---

## Terminology

| Concept            | Term in code        | Notes                                                     |
| ------------------ | ------------------- | --------------------------------------------------------- |
| Run                | `run`               | One call to `Engine.run()` or one CLI invocation          |
| Config package     | `config_package`    | Installed `ade_config` package for this run               |
| Config version     | `manifest.version`  | Version declared by the config package manifest           |
| Build              | build               | Virtual environment built for a specific config version   |
| User data file     | `source_file`       | Original spreadsheet on disk                              |
| User sheet         | `source_sheet`      | Worksheet/tab in the spreadsheet                          |
| Canonical column   | `field`             | Defined in manifest; never call this a “column”           |
| Physical column    | column              | B / C / index 0,1,2… in a sheet                           |
| Output workbook    | normalized workbook | Written to `output_dir`; includes mapped + normalized data|

Use these names everywhere in code comments, telemetry, docs, and filenames.
Avoid synonyms like “input file” (use **source file**), “output file” (say
**output workbook** or explicitly refer to telemetry), or mixing “field”
and “column”. Backend notions like run request/workspace/tenant remain outside
the engine and only show up as opaque metadata if the caller passes them.

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
   - an **`events.ndjson`** telemetry stream (ADE events using `ade.event/v1`)
   - a `RunResult` object describing status, outputs, and logs (no artifact file)

The engine itself is **business‑logic free**: all domain rules live in
`ade_config`.

In production, the ADE API:

- builds a **frozen venv** per config (`ade_engine` + a specific `ade_config` version),
- then, for each **run request**, launches a worker (process or thread) inside that venv,
- and calls the engine with **file paths** (source / output / logs).

From the engine’s perspective, it just runs synchronously inside an isolated
environment with `ade_config` installed; **it is run‑scoped only—run IDs and
workspace concepts belong to the backend**. The ADE API later replays
`events.ndjson`, assigns `event_id`/`sequence`, and streams the events to
clients.

---

### Excel support (openpyxl)

The engine uses **openpyxl** for Excel IO:

- **Supported formats** — Excel Open XML only: `xlsx`, `xlsm`, `xltx`, `xltm`.
  Older `xls` is not supported and is rejected.
- **Source files are read‑only** — workbooks are opened with `read_only=True`
  and never saved back; the engine always writes a new normalized workbook.
- **Performance posture** — openpyxl in normal mode can use significant memory
  (docs note ~50× file size). The engine reads in streaming mode and keeps
  writes simple, but very large outputs still consume RAM proportionally.

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
    - writes the normalized workbook (e.g., `normalized.xlsx`) and
      `events.ndjson` to the given output/logs dirs.

The **engine does not know or care about backend run IDs**. It only needs:

- the config to use (`config_package`, `manifest_path`),
- one or more **source files**,
- where to write the output workbook(s) and logs.

The ADE API is responsible for mapping those paths back to any run record in
its own database.

The engine has **no knowledge** of:

- the ADE API,
- workspaces, config package registry, or queues,
- backend run requests or their IDs,
- how many threads/processes are running.

It is a pure “source files → normalized workbook + logs” component. The backend
may choose to associate one backend run request with one or many runs; that
mapping stays outside the engine.

---

## 2. Package layout (layered and obvious)

Make the layering explicit with clear subpackages:

```text
ade_engine/
  core/                      # Runtime orchestrator + pipeline
    __init__.py              # Re-export Engine, RunRequest, RunResult, etc.
    engine.py                # Engine.run orchestration
    types.py                 # RunRequest, RunResult, RunContext, ExtractedTable, enums (core runtime models)
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

  infra/                     # IO + telemetry plumbing (artifact helper lives here but is optional/legacy)
    io.py
    artifact.py              # legacy/optional artifact sink
    telemetry.py

  schemas/                   # Python-first schemas (Pydantic)
    __init__.py
    manifest.py
    telemetry.py             # ade.event/v1 envelope + run/build/run-summary models as needed
    artifact.py

  cli/                       # Typer-based CLI (`ade-engine`) with subcommands
    __init__.py
    app.py                   # Typer app wiring
    commands/                # One file per command for maintainability
      run.py                 # primary run command
      version.py             # prints version
  __main__.py                # `python -m ade_engine` → cli.app()

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

* Runtime/core depends on config types and infra helpers.
* `config/` (formerly `config_runtime/`) can depend on schemas and infra where
  needed.
* `infra/` holds IO + telemetry plumbing (artifact sink remains for optional/legacy use).
* `cli/` is a thin wrapper over the public API; keep business logic in `core/`.
* Hooks remain part of the core extension model via `config/hook_registry.py`
  (legacy path: `config_runtime/hook_registry.py`); hook invocation helpers can
  live in `core/` if desired.

If you know this layout, you know where everything lives:

* **How do I run the engine?** → `core/engine.py`, `ade_engine/__init__.py`
* **How do we load config scripts?** → `config/loader.py`
* **How does the pipeline work?** → `core/pipeline/`
* **Where is telemetry written?** → `infra/telemetry.py` (artifact helper in `infra/artifact.py` if needed)

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

You only need to dig into `pipeline` or `telemetry` if you are
working on the engine internals (artifact sink is optional/legacy).

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

(unchanged from your current docs, just summarized here)

The core runtime types (`RunRequest`, `RunResult`, `RunContext`, `RunPaths`,
`RunPhase`, `RunStatus`, `RunError`, `RunErrorCode`, `ExtractedTable`, `MappedTable`,
`NormalizedTable`, etc.) are already documented in
`docs/01-engine-runtime.md`. This README just points you there.

* **Run-level types and lifecycle:** see
  `apps/ade-engine/docs/01-engine-runtime.md`.
* **Table and pipeline types:** see
  `apps/ade-engine/docs/03-io-and-table-detection.md`,
  `04-column-mapping.md`, `05-normalization-and-validation.md`.

We keep **field vs column** terminology consistent across all these docs.

---

## 4. Config packages (`ade_config`) and manifest

Config packages and the manifest schema are documented in detail in
`02-config-and-manifest.md`. Key points:

* One `ade_config` package per config build, installed into the same venv as
  `ade_engine`.
* Manifest is JSON (or TOML/YAML) but defined as Python models in
  `ade_engine.schemas.manifest`.
* Config code lives in:

  * `row_detectors` (row finding),
  * `column_detectors` (field detection + transforms + validators),
  * `hooks` (lifecycle hooks).

See `apps/ade-engine/docs/02-config-and-manifest.md` for the manifest model and
how the config runtime works.

---

## 5. How the engine runs

The mechanics of `Engine.run` are documented in
`docs/01-engine-runtime.md`:

* Normalize `RunRequest` ➜ `RunPaths` + `RunContext`.
* Load config runtime (`load_config_runtime`) and manifest.
* Initialize telemetry sink (event log).
* Execute pipeline via `execute_pipeline()`:

  * `extract` ➜ `ExtractedTable[]`
  * `mapping` ➜ `MappedTable[]`
  * `normalize` ➜ `NormalizedTable[]`
  * `write` ➜ workbook(s)
* Run hooks (`on_run_start`, `on_after_extract`, `on_after_mapping`,
  `on_before_save`, `on_run_end`).
* Return `RunResult`.

The engine is **logically stateless** at the instance level; all
per‑run state lives on `RunContext`.

See `01-engine-runtime.md` for the full lifecycle and error handling details.

---

## 6. Pipeline stages (`pipeline/`)

The pipeline is broken into obvious stages:

* `extract.py` – IO + row detectors → `ExtractedTable`.
* `mapping.py` – column detectors + scoring → `MappedTable`.
* `normalize.py` – transforms + validators → `NormalizedTable`.
* `write.py` – produce the normalized workbook(s).
* `pipeline_runner.py` – orchestrate phases; emits phase transitions via telemetry.

Detailed docs for each stage are in:

* `03-io-and-table-detection.md`
* `04-column-mapping.md`
* `05-normalization-and-validation.md`

---

## 7. Telemetry (`events.ndjson`)

Telemetry is the engine’s only structured output besides the normalized
workbook(s). Events use the `AdeEvent` envelope defined in
`ade_engine/schemas/telemetry.py`:

```jsonc
{
  "type": "run.table.summary",
  "created_at": "2025-11-26T12:34:56Z",
  "sequence": 7,                // optional in engine output; added by API when replayed
  "workspace_id": "ws_123",     // from RunRequest.metadata when provided
  "configuration_id": "cfg_123",
  "run_id": "run_123",
  "payload": {
    "table_id": "tbl_0",
    "source_file": "input.xlsx",
    "source_sheet": "Sheet1",
    "table_index": 0,
    "row_count": 10,
    "unmapped_column_count": 1,
    "validation": {"total": 3, "by_severity": {"error": 2, "warning": 1}},
    "mapping": {...}
  }
}
```

Key events the engine emits:

- `console.line` — via `PipelineLogger.note`; payload has `scope:"run"`, `stream`, `level`, `message`.
- `run.started` — emitted at the start of `Engine.run` with `status:"in_progress"` and `engine_version`.
- `run.table.summary` — one per normalized table with mapping + validation breakdowns.
- `run.validation.summary` — aggregated validation counts (optional, emitted when there are issues).
- `run.validation.issue` — optional per-issue events.
- `run.error` — structured error context when an exception is mapped to `RunError`.
- `run.completed` — terminal status with `status`, `output_paths`, `processed_files`, and optional `error`.

How it’s written:

- Default sink: `FileEventSink` created by `TelemetryConfig.build_sink` (writes to `<logs_dir>/events.ndjson`).
- Sequence/event_id: not set by the engine; the ADE API re-envelops engine events, assigns `event_id`/`sequence`, and persists them to dispatcher-backed logs for streaming.

Engine-side API surface (`PipelineLogger`):

- `note(message, level="info", stream="stdout", **details)` → `console.line`.
- `event(type_suffix, level=None, **payload)` → emits `run.<type_suffix>`.
- `pipeline_phase(phase, **payload)` → convenience for `run.phase.started` (only “started” is emitted today).
- `record_table(table)` → emits `run.table.summary`.
- `validation_issue(**payload)` / `validation_summary(issues)` → emit validation events.

For the detailed taxonomy and payloads used by ADE, see
`apps/ade-engine/docs/07-telemetry-events.md` and
`apps/ade-engine/docs/11-ade-event-model.md`.

---

## 8. Script API overview (config side)

The script API (detectors, transforms, validators, hooks) is documented in the
per‑chapter docs:

* Row detectors: `03-io-and-table-detection.md`
* Column detectors & mapping: `04-column-mapping.md`
* Transforms & validators: `05-normalization-and-validation.md`
* Hooks: `08-hooks-and-extensibility.md`

All entrypoints are keyword‑only, receive `RunContext` as `run` plus a
per‑run `state` dict, and are designed to be forward‑compatible via `**_`.

---

## 9. CLI & integration

The CLI’s contract (`ade-engine run ...`) and how the ADE API calls it inside
venvs is documented in `09-cli-and-integration.md`.

Key ideas:

* CLI is a thin wrapper over `Engine.run()`.
* It prints a JSON summary mirroring `RunResult`.
* Non‑zero exit code means the run failed or CLI usage was invalid.

---

## 10. Design principles

This architecture is intentionally:

* **Config‑centric** – ADE engine is a generic spreadsheet pipeline,
  driven entirely by `ade_config` (manifest + scripts).
* **Path‑based, run‑scoped** – the engine deals in **files and folders**
  only. Higher‑level orchestration (run requests, queues, retries) lives in
  the ADE API.
* **Predictable** – All public entry points and file names follow standard
  patterns:

  * `Engine.run`, `RunRequest`/`RunResult`
  * `execute_pipeline()`, `extract.py`, `mapping.py`, `normalize.py`,
    `write.py`
  * `infra/io.py`, `config/loader.py`, `config/hook_registry.py`
    (legacy: `config_runtime/*`), `infra/telemetry.py`
* **Python‑first schemas** – Manifest, telemetry, and run summary schemas are
  defined as Python models (Pydantic), with JSON Schemas generated as needed.
  See `docs/07-telemetry-events.md`, `docs/11-ade-event-model.md`,
  `docs/12-run-summary-and-reporting.md`.
* **Auditable** – Every detector score, transform, and validation issue can be
  explained via `events.ndjson` and derived run summaries.
* **Isolated & composable** – Each config build gets its own venv; each engine
  call runs inside that venv, so changes to one config or environment never
  leak into others.
* **Extensible** – Hooks, ADE events, and run summaries support evolving needs
  without changing the engine core.

With this README and the folder layout above, you should be able to reason
about the engine from scratch and confidently implement or refactor any part of
it.

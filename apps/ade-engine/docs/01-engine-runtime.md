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
> a **normalized workbook + artifact + telemetry**, with no knowledge of backend jobs.

From inside the venv, the engine:

- Accepts a **config** to use (`config_package`, optional `manifest_path`).
- Accepts **inputs** (`input_files` or `input_root`, optional `input_sheets`).
- Accepts where to put **outputs** (`output_root`, `logs_root`).
- Accepts opaque **metadata** from the caller (e.g., backend job IDs if desired).

It emits:

- One or more **normalized Excel workbooks** in `output_root`.
- An **artifact JSON** (`artifact.json`) in `logs_root`.
- **Telemetry events** (`events.ndjson`) in `logs_root`.
- A **`RunResult`** describing the outcome.

The engine **does not**:

- Know about backend job queues, tenants, workspaces, or job IDs.
- Own virtual environment creation, scaling, or scheduling.
- Enforce OS‑level limits (CPU, memory, time). That’s handled by the backend.

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

`RunContext` is what config code receives as the `run` argument. It contains:

* `run_id: str`
  Unique identifier per run (e.g. UUID).

* `paths: RunPaths`
  Fully resolved filesystem layout.

* `manifest: ManifestContext`
  Wrapper around the loaded manifest (Pydantic model + convenience helpers).

* `env: dict[str, str]`
  From `manifest.env`. This is the config‑level environment, not OS env vars.

* `metadata: dict[str, Any]`
  Copy of `RunRequest.metadata`. The engine treats this as an opaque dict (e.g., a backend `job_id` if provided).

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

     * `run` (`RunContext`),
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

      * `run` (`RunContext`),
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

The runtime is intentionally simple and **backend‑job‑agnostic**. The typical backend
integration looks like this:

1. ADE backend decides which config version to use.

2. Backend ensures a venv exists with:

   * `ade_engine`,
   * that specific `ade_config` version.

3. Backend prepares a per‑run working directory (often under a job folder), e.g.:

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
     `events.ndjson` in its own job/task record.
   * Uses `artifact.json` and `events.ndjson` for reporting and UI.

The engine never needs to know what `job_id` means; it just sees file paths and
optional metadata for the run.

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

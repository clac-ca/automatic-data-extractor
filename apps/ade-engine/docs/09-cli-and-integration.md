# CLI and Integration with ADE API

This document describes the command‑line interface to the ADE engine and how
the ADE backend invokes it inside a virtual environment.

It assumes you’ve read `ade_engine/README.md` and understand that the engine
is **path‑based and backend‑job‑agnostic**: it sees source/output/log paths and opaque
metadata for telemetry correlation, not job IDs or queues in its own models.

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

The CLI is exposed as a console script:

```bash
ade-engine ...
```

`python -m ade_engine` delegates to the same Typer app (`ade_engine.cli.app`). The CLI **does not** create or manage
virtual environments; it assumes the current interpreter is already running
inside the correct venv (`ade_engine` + the desired `ade_config`).

---

## 3. Argument model

The CLI maps directly to `RunRequest` fields. Conceptually:

```bash
ade-engine run \
  [SOURCE SELECTION] \
  [OUTPUT / LOGS] \
  [CONFIG OPTIONS] \
  [METADATA]
```

### 3.1 Source selection (mutually exclusive)

Exactly one of these must be provided:

* `--input PATH` (repeatable)
  One or more explicit source files:

  ```bash
  --input /data/jobs/123/input/input.xlsx
  --input /data/jobs/123/input/other.xlsx
  ```

  → `RunRequest.input_files = [Path(...), Path(...)]`

* `--input-dir DIR`
  Directory to scan for source spreadsheets (`.csv`, `.xlsx`):

  ```bash
  --input-dir /data/jobs/123/input
  ```

  → `RunRequest.input_dir = Path(...)`

If both `--input` and `--input-dir` are provided, the CLI fails fast with a
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
  → `RunRequest.output_dir = Path(DIR)`

* `--logs-dir DIR`
  → `RunRequest.logs_dir = Path(DIR)`

If omitted, the engine may infer sensible defaults from the input location
(e.g. sibling `output/` and `logs/` directories), but backend workers should
**explicitly pass both** to keep backend layout predictable.

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

### 3.5 Metadata (optional)

* `--metadata KEY=VALUE` (repeatable, if supported)
  For injecting simple tags into `RunRequest.metadata`:

  ```bash
  --metadata job_id=abc123 \
  --metadata config_id=config-01
  ```

  The engine treats metadata as opaque; it mirrors it into
  `RunContext.metadata` and telemetry envelopes (not into `artifact.json`). How those
  keys relate back to “jobs” is entirely a backend concern.

---

## 4. Non‑run commands

The CLI also supports simple non‑run queries:

* `--version`
  Print engine version (and optionally config manifest version if discoverable)
  and exit with code `0`. No pipeline is executed.

* `--manifest-path PATH` without any `--input`/`--input-dir`
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
    "id": "run-uuid",
    "status": "succeeded",
    "output_paths": ["/data/jobs/123/output/normalized.xlsx"],
    "artifact_path": "/data/jobs/123/logs/artifact.json",
    "events_path": "/data/jobs/123/logs/events.ndjson",
    "processed_files": ["input.xlsx"],
    "error": null
  }
}
```

Fields mirror `RunResult`:

* `status`: `"succeeded"` or `"failed"`.
* `output_paths`: list of output workbook paths (usually 1).
* `artifact_path`: path to `artifact.json`.
* `events_path`: path to `events.ndjson`.
* `processed_files`: basenames of source files the engine actually read.
* `error`: `null` on success, or a human‑readable error summary on failure.

The ADE backend should **not parse internal error messages** for control flow;
it should rely on `status` and the presence of the log files. Error messages
are for logs and operator visibility.

### 5.2 Exit codes

* `0`

  * All non‑run commands completed successfully, or
  * Run finished and `status == "succeeded"`.

* Non‑zero

  * CLI usage error (e.g. both `--input` and `--input-dir`), or
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

2. **Backend resolves job/task** to a venv and per-run paths:

   * Ensure a venv exists for `<config_id>/<build_id>` with:

     * `ade_engine` installed.
     * the appropriate `ade_config` version installed.
   * Create a backend job directory (with a per-run working area):

     ```text
     /data/jobs/<job_id>/
       input/
         input.xlsx
       output/
       logs/
     ```

3. **Backend schedules worker** (thread/process/container) with:

   * venv location,
   * backend job directory paths (input/output/logs for this run),
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
         output_dir=Path(f"/data/jobs/{job_id}/output"),
         logs_dir=Path(f"/data/jobs/{job_id}/logs"),
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
* `examples/logs/artifact.json` — mapping, validation, and run details (no backend metadata).
* `examples/logs/events.ndjson` — telemetry stream.

### 7.2 Python from a REPL or test

Example:

```python
from pathlib import Path
from ade_engine import run

result = run(
    input_files=[Path("examples/input.xlsx")],
    output_dir=Path("examples/output"),
    logs_dir=Path("examples/logs"),
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

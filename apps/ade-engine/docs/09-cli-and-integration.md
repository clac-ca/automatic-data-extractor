# CLI and Integration with ADE API

This document describes the command‑line interface to the ADE engine and how
the ADE backend invokes it inside a virtual environment.

It assumes you’ve read `ade_engine/README.md` and understand that the engine
is **path‑based and backend-run-agnostic**: it sees source/output/log paths, not run queues
or orchestration state in its own models.

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

CLI help text should stick to this vocabulary: “input files” refers only to
CLI parameters (`--input/--input-dir`), while “source files” describe the user
spreadsheets being processed.

---

## 1. Goals of the CLI

The CLI is a thin, stable wrapper around `Engine.run()` that:

- Accepts **file system paths and options** as flags.
- Construct a `RunRequest`.
- Executes a single pipeline run.
- Emits an **NDJSON stream of engine events** to stdout (parse the final `engine.complete` frame for status).
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

The CLI maps directly to `RunRequest` fields plus output-formatting toggles. Conceptually:

```bash
ade-engine run \
  [SOURCE SELECTION] \
  [OUTPUT / LOGS] \
  [CONFIG OPTIONS] \
  [OUTPUT FORMAT / SUMMARIES]
```

### 3.1 Source selection

Provide at least one source via `--input` and/or `--input-dir` (they’re merged,
de‑duplicated, and sorted):

* `--input PATH` (repeatable) — explicit source file(s).
* `--input-dir PATH` — recurse a directory of inputs.
  * `--include PATTERN` — glob(s) applied under `--input-dir` (default: `*.xlsx`, `*.csv`).
  * `--exclude PATTERN` — glob(s) to skip under `--input-dir`.

→ Each input triggers a separate run. Outputs/events are written to the
  specified paths (or per-input subdirectories when you pass multiple inputs with a shared
  `--output-dir`/`--logs-dir`).

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

### 3.3 Output and events

Where to write normalized workbooks and optional engine events:

* `--output-file FILE`
  → Write the normalized workbook to an explicit path.

* `--output-dir DIR`
  → If no `--output-file` is provided, default to `DIR/normalized.xlsx`.
    If omitted, defaults to `<input_dir>/output/normalized.xlsx`.

* `--logs-file FILE`
  → Write engine NDJSON events to this path. No file sink is created unless this is set (or `--logs-dir` is provided).

* `--logs-dir DIR`
  → If no `--logs-file` is provided, default to `DIR/engine_events.ndjson`.
    If omitted, the engine only emits events to stdout.

### 3.4 Config selection

Config package:

* `--config-package NAME_OR_PATH` (optional; default: `ade_config`)

  ```bash
  --config-package ade_config           # use installed package
  --config-package ./config-dir         # load config from a local directory containing ade_config/manifest.json
  ```

  → `RunRequest.config_package = "ade_config"` by default, or the provided module/path.
    When a path is provided, the engine will prepend the appropriate `sys.path`
    entry so `ade_config` can be imported and its `manifest.json` discovered.
    If no config is installed or the path does not contain `ade_config/manifest.json`,
    the CLI raises a config error.

### 3.5 Output formatting and summaries

* `--quiet / --no-quiet` — suppress NDJSON on stdout; file sinks still honored.
* `--format [text|json]` — `text` (default) streams NDJSON and prints a final run
  summary; `json` emits a single JSON object per run (or a single aggregate JSON when requested).
* `--aggregate-summary` — print an aggregate summary across inputs (table in text mode; JSON in json mode).
* `--aggregate-summary-file PATH` — write aggregate summary JSON to a path (regardless of stdout format).

---

## 4. Non‑run commands

The CLI also supports simple non‑run queries:

* `version`
  Print engine version (and optionally config manifest version if discoverable)
  and exit with code `0`. No pipeline is executed.
  You may pass `--manifest-path` to print a specific manifest version.

---

## 5. Output format and exit codes

### 5.1 Text mode (default)

* Streams **one JSON object per line** (NDJSON) to stdout unless `--quiet`.
  Key frames:

  * `engine.start` — indicates config version and engine version.
  * `engine.complete` — final status and artifacts (output path, processed file).

* Prints a concise run summary after all inputs complete (and an aggregate view when `--aggregate-summary` is set).

When `--logs-file`/`--logs-dir` is explicitly provided, the engine also writes a local copy
(`engine_events.ndjson`) so you can inspect events without scraping stdout. Normalized workbooks
are written to the configured output path (`--output-file` or `--output-dir/normalized.xlsx`).

The ADE backend should **not parse internal error messages** for control flow;
it should rely on `status` and the presence of the event log. Error messages
are for logs and operator visibility.

### 5.2 JSON mode

* Suppresses NDJSON on stdout.
* Emits **one JSON object per run** (or a single aggregate JSON object when `--aggregate-summary` is set).
* Combine with `--aggregate-summary-file` to persist the aggregate payload alongside stdout.

### 5.3 Exit codes

* `0`

  * All non‑run commands completed successfully, or
  * Run finished and `status == "succeeded"`.

* Non‑zero

  * CLI usage error (e.g. both `--input` and `--input-dir`), or
  * Run failed and `status == "failed"`.

The exact non‑zero values are not intended as a stable API; backend code
should treat any non‑zero as “run/CLI failed” and use the JSON summary +
log files for details.

### 5.4 Common invocations

```bash
# Single file (text mode, NDJSON to stdout)
ade-engine run \
  --config-package ade_config \
  --input /data/runs/<id>/input/input.xlsx \
  --output-dir /data/runs/<id>/output \
  --logs-dir /data/runs/<id>/logs

# Batch via shell glob
ade-engine run \
  --config-package ade_config \
  --output-dir /tmp/ade-out \
  --logs-dir /tmp/ade-logs \
  $(printf -- '--input %q ' /data/samples/*.xlsx)

# Directory scan with include/exclude filters
ade-engine run \
  --config-package ade_config \
  --input-dir /data/samples \
  --include '*.xlsx' --exclude '*~' \
  --output-dir /tmp/ade-out \
  --logs-dir /tmp/ade-logs

# JSON-only with quiet + aggregate summary
ade-engine run \
  --config-package ade_config \
  --input-dir /data/samples \
  --include '*.xlsx' \
  --output-dir /tmp/ade-out \
  --logs-dir /tmp/ade-logs \
  --quiet \
  --format json \
  --aggregate-summary \
  --aggregate-summary-file /tmp/ade-agg.json
```

---

## 6. Integration with ADE backend

### 6.1 Worker lifecycle (typical)

A typical end‑to‑end flow:

1. **API request** arrives:
   “Run config `<config_id>` on uploaded document `<document_id>`.”

2. **Backend resolves the run request** to a venv and per-run paths:

   * Ensure a venv exists for `<config_id>/<build_id>` with:

     * `ade_engine` installed.
     * the appropriate `ade_config` version installed.
  * Create a backend run directory (with a per-run working area):

    ```text
    /data/runs/<run_id>/
      input/
        input.xlsx
      output/
      logs/
    ```

3. **Backend schedules worker** (thread/process/container) with:

   * venv location,
  * backend run directory paths (input/output/logs for this run),
   * config identifier.

4. **Worker activates venv** and invokes the engine, either:

   * **CLI**:

     ```bash
     /path/to/.venv/<config_id>/<build_id>/bin/python -m ade_engine \
       run \
       --input /data/runs/<run_id>/input/input.xlsx \
       --output-dir /data/runs/<run_id>/output \
       --logs-dir /data/runs/<run_id>/logs \
       --config-package ade_config \
       --quiet \
       --format json
     ```

   * **Python API** (equivalent):

     ```python
     from pathlib import Path
     from ade_engine import run

     result = run(
         config_package="ade_config",
         input_file=Path(f"/data/runs/{run_id}/input/input.xlsx"),
         output_dir=Path(f"/data/runs/{run_id}/output"),
         logs_dir=Path(f"/data/runs/{run_id}/logs"),
     )
     ```

5. **Worker updates backend state**:

   * Parse CLI JSON or inspect `RunResult`.
   * Persist:

     * output workbook path(s),
     * `events.ndjson` path (under `logs_dir`),
     * status (`succeeded` / `failed`).
   * Optionally parse `events.ndjson` to drive UI and reporting; build a run
     summary (`ade.run_summary/v1`) from events.

Importantly, the engine:

* Never needs to know queue semantics or workspace tenancy beyond the paths and config provided for a run.
* Treats run/workspace/config identifiers as caller-provided context, not engine state.

### 6.2 Python API vs CLI

Both are first‑class and interchangeable:

* **CLI**:

  * Natural fit for process‑oriented workers or containerized run executors.
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
* `examples/logs/events.ndjson` — telemetry stream (run + table summaries).

### 7.2 Python from a REPL or test

Example:

```python
from pathlib import Path
from ade_engine import run

result = run(
    input_file=Path("examples/input.xlsx"),
    output_dir=Path("examples/output"),
    logs_dir=Path("examples/logs"),
)

print(result.status, result.output_path)
```

Both workflows use the same engine and produce the same outputs/telemetry; only
the calling mechanism differs.

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
paths and caller-provided context; all higher‑level security and scheduling policies
live in the ADE API layer.

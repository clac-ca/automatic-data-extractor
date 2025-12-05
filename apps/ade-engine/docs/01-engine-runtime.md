# ADE Engine Runtime

This document describes what a **single ADE engine run** is, how it is invoked
(programmatic + CLI), and how the core runtime types (`RunRequest`,
`RunContext`, `RunResult`) fit together in the new **events-only** contract.

The engine now produces **only** normalized outputs and telemetry events.
Run summaries are derived downstream (e.g., by `ade-api`) from the event log.

## 1. Purpose and boundaries

A single engine run is:

> A pure, path-based function that takes **config + source files** and produces
> a **normalized workbook + telemetry events**, with no backend awareness.

What the engine accepts:

- **Config package**: `config_package` (defaults to `ade_config`) and optional `manifest_path`.
- **Source**: a single `input_file` (plus optional `input_sheets` for XLSX).
- **Outputs**: `output_dir` for workbooks; `logs_dir` for telemetry.
- **Metadata**: opaque keys (workspace_id, configuration_id, run_id, etc.) for telemetry correlation only.

What the engine emits:

- One or more **normalized workbooks** under `output_dir`.
- **Telemetry events** (`events.ndjson`) under `logs_dir` using the `ade.event/v1` envelope.
- A **`RunResult`** that surfaces status, run id, output paths, processed files, and `logs_dir`.

The engine **does not**:

- Own run orchestration, virtual environment setup, or scheduling.
- Persist a run summary. That is derived by a service (e.g., `ade-api`) from the event log.
- Require or emit `artifact.json`. The legacy artifact file is no longer part of the contract.

## 2. Entry points

### Programmatic API (`Engine` and `run`)

```python
from pathlib import Path
from ade_engine import Engine, run, RunRequest

engine = Engine()
result = engine.run(
    RunRequest(
        config_package="ade_config",
        input_file=Path("input.xlsx"),
        output_dir=Path("output"),
        logs_dir=Path("logs"),
        metadata={"run_id": "123"},  # opaque tags for telemetry
    )
)

# Convenience helper
result = run(input_file=Path("input.xlsx"), output_dir=Path("output"), logs_dir=Path("logs"))
```

Characteristics:

- `Engine` is stateless and safe to reuse across threads if each call uses its own `RunRequest`.
- The top-level `run(...)` helper builds a `RunRequest`, creates a short-lived `Engine`, and returns a `RunResult`.

### CLI (`python -m ade_engine`)

```bash
python -m ade_engine \
  --input ./input.xlsx \
  --output-dir ./output \
  --logs-dir ./logs \
  --config-package ade_config
```

The CLI parses flags into a `RunRequest`, runs the engine once, prints a JSON
summary (status, run_id, output_path, logs_dir, events_path) to stdout, and
exits non-zero on failure. See `09-cli-and-integration.md` for flag details.

## 3. Core runtime types

### `RunRequest` – “what to run”

- `config_package: str` — importable package name (default: `ade_config`).
- `manifest_path: Path | None` — optional override for `ade_config/manifest.json`.
- `input_file: Path | None` — single source selection (required).
- `input_sheets: Sequence[str] | None` — optional sheet filter for XLSX.
- `output_dir: Path | None` — where normalized workbooks are written (default: `<input_file>/../output`).
- `logs_dir: Path | None` — where telemetry is written (default: `<input_file>/../logs`).
- `metadata: Mapping[str, Any] | None` — opaque telemetry tags.

Invariant: `input_file` must be provided; paths are normalized to absolute paths early in `Engine.run`.

### `RunPaths` – resolved filesystem layout

- `input_file: Path`
- `output_dir: Path`
- `logs_dir: Path`

Resolution rules:

1. Resolve `input_file` to an absolute path.
2. If `output_dir`/`logs_dir` are set, use them; otherwise, default to siblings of the input file (`output/`, `logs/`).
3. Directories are created on demand before pipeline execution (the parent directory for `input_file` is expected to already exist).

### `RunContext` – shared per-run state

Holds `run_id`, `metadata`, `manifest`, `paths`, timestamps, and a mutable
`state` dict for hook communication. `started_at` is set at the beginning of
`Engine.run`; `completed_at` is populated when the run finishes or fails.

### `RunResult` – outcome surface

- `status: RunStatus` (`succeeded` | `failed`)
- `error: RunError | None` — structured failure info when present
- `run_id: str`
- `output_path: Path | None`
- `logs_dir: Path`
- `processed_files: tuple[str, ...]`

Note: callers can derive `events.ndjson` as `logs_dir / "events.ndjson"`.

## 4. Runtime flow (happy path)

1. **Normalize request**: validate `input_file`, resolve `output_dir`/`logs_dir` next to it.
2. **Load config**: import `ade_config`, load `manifest.json`, build `ConfigRuntime`.
3. **Initialize telemetry**: build an `EventSink` (default `FileEventSink` writing to `logs/events.ndjson`), construct a run-scoped `EventEmitter`, and attach a run `logger` bridged to telemetry via `TelemetryLogHandler`.
4. **Run hooks (ON_RUN_START)**: give hooks access to `run`, `manifest`, `logger`, and mutable `state`.
5. **Extract**: discover and slice tables into `ExtractedTable` objects.
6. **Map**: score headers and build `MappedTable` objects.
7. **Normalize**: apply transforms/validators to produce `NormalizedTable` objects; emit `engine.table.summary` events that include row counts, mapped/unmapped columns, and validation breakdowns.
8. **Write outputs**: sort tables, write `normalized.xlsx` to `output_dir`.
9. **Emit completion**: emit `engine.table.summary` events as tables finish, aggregate into `engine.sheet.summary`/`engine.file.summary`, emit the final `engine.run.summary`, then emit `engine.complete` with status, output paths, processed files, and any error payload.
10. **Run hooks (ON_RUN_END)**: allow post-processing with access to `result`, `tables`, `logger`.

Failures are mapped to `RunError` with a consistent `code`/`message`/`stage`
and surfaced via telemetry and `RunResult.error`. `engine.complete` is emitted
even on failures when a sink is available.

## 5. Telemetry and run summaries

- The **only engine-owned schema** is `ade.event/v1`, written as NDJSON to `logs_dir/events.ndjson`.
- Each event includes `workspace_id`/`configuration_id` when present in `RunRequest.metadata`.
- The engine emits the authoritative `RunSummary` as `engine.run.summary` before `engine.complete`; downstream services should persist this payload instead of recomputing from logs.

## 6. Hooks and extensibility

Hooks are configured in the manifest (`on_run_start`, `on_after_extract`,
`on_after_mapping`, `on_before_save`, `on_run_end`). The hook context now
exposes:

- `run`, `state`, `manifest`, `input_file_name` (with a `file_name` alias for compatibility)
- Optional `tables`, `workbook`, `result`
- `logger` (use `logger.note`, `logger.pipeline_phase`, `logger.record_table`)
- `event_emitter` (`config.*` namespace) for sparse custom telemetry

Hooks no longer receive artifact or raw event sink objects; telemetry is emitted through the logger or `event_emitter.custom(...)`.

## 7. Error handling

Exceptions are mapped to `RunError` using `error_to_run_error` with the
current `RunPhase`. On failure:

- `RunResult.status` is `failed` and `error` is populated.
- A `engine.complete` event with `status: "failed"` and structured error is emitted when telemetry is available.
- `logs_dir` is still returned so callers can inspect partial logs.

---

For API integration details (CLI JSON shape, orchestration, run summaries), see
`09-cli-and-integration.md` and `12-run-summary-and-reporting.md`.

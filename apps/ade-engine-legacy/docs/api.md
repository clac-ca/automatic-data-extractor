# Public API

This document describes the supported, stable API surface of `ade-engine`.

---

## Package exports (`ade_engine/__init__.py`)

`ade_engine` exports:

- `Engine`
- `Settings`
- `RunRequest`, `RunResult`, `RunStatus`
- `__version__`

### Engine

```python
from ade_engine import Engine
from ade_engine.types.run import RunRequest

engine = Engine()
result = engine.run(RunRequest(input_file=Path("source.xlsx")))
```

`Engine.run(...)` accepts either a `RunRequest` or keyword arguments used to build one.

Key parameters (high level):

- `request`: run configuration (input, outputs, config package)
- `logger`: logger instance (prefer `RunLogger` from `create_run_logger_context.logger` for structured `event` + `data` fields)

Return value: `RunResult` with status, output_path, logs_dir, and optional error details.

### RunRequest

RunRequest fields include:

- `config_package` (module name or path; default `ade_config`)
- `manifest_path` (optional override for `manifest.toml`)
- `input_file` and optional `input_sheets`
- output: `output_dir`, `output_file`
- logs: `logs_dir`, `logs_file`

### RunResult

`RunResult` includes:

- `status`: `running|succeeded|failed`
- `error`: `RunError` or `None`
- `output_path`: where the normalized workbook was written
- `logs_dir`: where logs/artifacts were written (best-effort)
- `processed_file`
- timestamps: `started_at`, `completed_at`

---

## Reporting API (`ade_engine.logging`)

`create_run_logger_context(namespace, log_format, log_file, log_level)` builds the run-scoped logging stack (text or ndjson) and returns a `RunLogContext` with:
- `logger`: `RunLogger` (a `LoggerAdapter`) that adds a default `event` (`<namespace>.log`) to plain log lines and wraps structured payloads under `data`. It also exposes `logger.event(name, message=None, level=..., **fields, exc=None)` for domain events.

Structured output (ndjson) uses ECS-ish keys:
- `timestamp`, `level`, `message`
- `event` (namespaced, e.g., `engine.run.started` or `engine.log`)
- `data` (flexible payload)
- `error` dictionary when exceptions are logged (`type`, `message`, `stack_trace`)
The same shape is SSE-friendly: `event: <name>` and `data: { ... }`.

Examples:

Plain log (no explicit event):

```python
logger.debug("Run starting", extra={"data": {"input_file": "source.xlsx"}})
```

```json
{
  "timestamp": "2025-12-09T17:30:44.726Z",
  "level": "debug",
  "message": "Run starting",
  "event": "engine.log",
  "data": {"input_file": "source.xlsx"}
}
```

Domain event:

```python
logger.event("run.started", message="Run started", input_file="source.xlsx", config_package="default")
```

```json
{
  "timestamp": "...",
  "level": "info",
  "message": "Run started",
  "event": "engine.run.started",
  "data": {
    "input_file": "source.xlsx",
    "config_package": "default"
  }
}
```

---

## Config callable API

All config callables are invoked through `PluginInvoker`, which provides a stable set of keyword-only arguments:

Common kwargs:
- `run`: `RunContext` (source/output workbooks, manifest, state)
- `state`: run state dict (mutable)
- `manifest`: `ManifestContext`
- `logger`: logger instance (`RunLogger` with `.event(...)`)
- `input_file_name`: basename of the source file

Plus stage-specific kwargs (examples):
- column detectors: `header`, `column_values`, `column_values_sample`, `extracted_table`…
- transforms/validators: `row_index`, `field_name`, `value`, `row`, `field_config`…
- row detectors: `row_index`, `row_values`, `values`…

Config callables must:
- declare keyword-only parameters
- accept `**_` for forward compatibility

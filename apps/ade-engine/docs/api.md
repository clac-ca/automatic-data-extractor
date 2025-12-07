# Public API

This document describes the supported, stable API surface of `ade-engine`.

---

## Package exports (`ade_engine/__init__.py`)

`ade_engine` exports:

- `ADEngine`
- `Settings`
- `RunRequest`, `RunResult`, `RunStatus`
- `__version__`

### ADEngine

```python
from ade_engine import ADEngine
from ade_engine.types.run import RunRequest

engine = ADEngine()
result = engine.run(RunRequest(input_file=Path("source.xlsx")))
```

`ADEngine.run(...)` accepts either a `RunRequest` or keyword arguments used to build one.

Key parameters (high level):

- `request`: run configuration (input, outputs, config package)
- `logger`: standard `logging.Logger` (optional)
- `event_emitter`: object with `.emit(event, **fields)` (optional)

Return value: `RunResult` with status, run_id, output_path, logs_dir, and optional error details.

### RunRequest

RunRequest fields include:

- `run_id` (optional UUID; if omitted, one is generated)
- `config_package` (module name or path; default `ade_config`)
- `manifest_path` (optional override for `manifest.toml`)
- `input_file` and optional `input_sheets`
- output: `output_dir`, `output_file`
- logs: `logs_dir`, `logs_file`
- `metadata` (included in `RunContext.state` and emitted events)

### RunResult

`RunResult` includes:

- `status`: `running|succeeded|failed`
- `error`: `RunError` or `None`
- `run_id`
- `output_path`: where the normalized workbook was written
- `logs_dir`: where logs/artifacts were written (best-effort)
- `processed_file`
- timestamps: `started_at`, `completed_at`

---

## Reporting API (`ade_engine.reporting`)

### EventEmitter
`EventEmitter.emit(event, **fields)` writes a structured event.

Reserved top-level fields:
- `ts`: UTC timestamp (added automatically)
- `event`: event name (string)
- `run_id`: run identifier (if provided)
- `meta`: run-level metadata dict (if provided)
- `message`, `level`, `stage`, `logger`
- `data`: remaining fields

Example:

```python
emitter.emit(
    "table.mapped",
    message="Mapped fields",
    sheet_name="Sheet1",
    table_index=0,
    mapped_fields=12,
)
```

### build_reporting(fmt, run_id, meta, file_path)
Creates a `Reporter` containing:
- a `logging.Logger` that emits structured `log` events
- an `EventEmitter`

---

## Config callable API

All config callables are invoked through `PluginInvoker`, which provides a stable set of keyword-only arguments:

Common kwargs:
- `run`: `RunContext` (source/output workbooks, manifest, state)
- `state`: run state dict (mutable)
- `manifest`: `ManifestContext`
- `logger`: logger instance
- `event_emitter` (and alias `events`): structured emitter
- `file_name` / `input_file_name`

Plus stage-specific kwargs (examples):
- column detectors: `header`, `column_values`, `column_values_sample`, `extracted_table`…
- transforms/validators: `row_index`, `field_name`, `value`, `row`, `field_config`…
- row detectors: `row_index`, `row_values`, `values`…

Config callables must:
- declare keyword-only parameters
- accept `**_` for forward compatibility

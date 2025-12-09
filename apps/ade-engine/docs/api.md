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
- `logger`: standard `logging.Logger` (optional)
- `events`: object with `.emit(event, **fields)` (optional)

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

## Reporting API (`ade_engine.logger`)

### EventEmitter
`EventEmitter.emit(event, **fields)` writes a structured event.

Reserved top-level fields:
- `ts`: UTC timestamp (added automatically)
- `event`: event name (string)
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

### start_run_logging(log_format, log_file, log_level)
Creates a `RunLogContext` containing:
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
- `events`: structured emitter
- `input_file_name`: basename of the source file

Plus stage-specific kwargs (examples):
- column detectors: `header`, `column_values`, `column_values_sample`, `extracted_table`…
- transforms/validators: `row_index`, `field_name`, `value`, `row`, `field_config`…
- row detectors: `row_index`, `row_values`, `values`…

Config callables must:
- declare keyword-only parameters
- accept `**_` for forward compatibility

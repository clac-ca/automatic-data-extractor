# Config Package Conventions

Config packages supply the domain logic the engine runs. A config package is any importable Python package (folder with `__init__.py`).

The engine auto-discovers plugin modules under:

- `<package>/columns/`
- `<package>/row_detectors/`
- `<package>/hooks/`

Any module in those folders with a top-level `register(registry)` function is imported and invoked (deterministic order; no central list).

## Minimal plugin module implementation

```python
# src/ade_config/columns/first_name.py
from ade_engine.models import FieldDef


def register(registry):
    registry.register_field(FieldDef(name="first_name", label="First Name", dtype="string"))
    # registry.register_column_detector(...)
    # registry.register_column_transform(...)
    # registry.register_column_validator(...)
```

Register everything imperatively using `registry.register_*` helpers inside module-level `register()` functions. You can keep shared helpers under `utils/` (or anywhere else), but the engine will not auto-import them unless a discovered module imports them.

## Suggested layout

```
src/ade_config/
  columns/          # one module per canonical field (detectors/transforms/validators)
  row_detectors/    # header/data voting
  hooks/            # lifecycle hooks
  utils/            # shared helpers
  __init__.py       # marks this folder as a Python package
```

This layout is not required, but auto-discovery only scans `columns/`, `row_detectors/`, and `hooks/`.

## Field metadata

Call `registry.register_field(FieldDef(...))` to declare labels, dtypes, or arbitrary metadata close to the logic that uses them. All fields must be registered before detectors/transforms/validators reference them.

## Settings for a package

Engine settings can be pinned alongside the package:
- Place a `settings.toml` next to your config package (and/or at the project root). The file is flat: keys map 1:1 to `Settings` fields.
- `.env` and `ADE_ENGINE_*` environment variables are also honored.
- Load via `Settings.load(...)`; precedence is documented in `apps/ade-engine/docs/settings.md`.

Commonly overridden settings per package:
- `remove_unmapped_columns` (drop non-canonical columns at write time)
- `write_diagnostics_columns` (include reserved `__ade_*` columns in output)
- `mapping_tie_resolution` (choose `leftmost` vs `leave_unmapped`)
- `detector_column_sample_size` (column detector sampling policy)
- `max_empty_rows_run` / `max_empty_cols_run` (sheet scanning guards)

## Testing your package

- Run a quick check with `python -m ade_engine process file --config-package <path> --input <file> --output-dir ./output --logs-dir ./logs`.
- If you omit `--logs-dir`, the engine logs only to stderr/stdout and does not write a log file.
- Keep a small fixture workbook in your repo and add a smoke test that uses `Engine(Settings())` with your package path.
- Use `--log-format ndjson --debug` to capture detector/transform telemetry while iterating.

## Packaging / installation

- The engine accepts either the package directory itself or a project root containing `src/<package>`.
- Editable installs work; the engine does not require the package name to be `ade_config`, but that is the default when multiple candidates exist under `src/`.

## Backward compatibility note

Legacy manifest-based wiring is no longer supported. All config logic must be registered explicitly inside module-level `register(registry)` functions using `registry.register_*`.

# Config Package Conventions

Config packages supply the domain logic the engine runs. A package is any importable Python package (folder with `__init__.py`) that exposes a `register(registry)` entrypoint.

## Minimal `register` implementation

```python
# src/ade_config/__init__.py
from . import columns, row_detectors, hooks

def register(registry):
    columns.register(registry)
    row_detectors.register(registry)
    hooks.register(registry)
```

Register everything imperatively inside `register(registry)` using `registry.register_*` helpers. There is no decorator-based auto-wiring.

## Suggested layout

```
src/ade_config/
  columns/          # one module per canonical field (detectors/transforms/validators)
  row_detectors/    # header/data voting
  hooks/            # lifecycle hooks
  utils/            # shared helpers
  __init__.py       # register() lives here
```

This layout is not required—the registry honors any structure as long as modules are imported inside `register()`.

## Field metadata

Call `registry.register_field(FieldDef(...))` to declare labels, dtypes, or arbitrary metadata close to the logic that uses them. All fields must be registered before detectors/transforms/validators reference them.

## Settings for a package

Engine settings can be pinned alongside the package:
- Place a `settings.toml` next to your package (or at the project root). A `[ade_engine]` table is recommended to avoid collisions.
- `.env` and `ADE_ENGINE_*` environment variables are also honored.
- Settings precedence: init kwargs > env vars > `.env` > `settings.toml` > defaults.

Commonly overridden settings per package:
- `append_unmapped_columns` / `unmapped_prefix` (control passthrough columns)
- `mapping_tie_resolution` (choose `leftmost` vs `leave_unmapped`)
- `max_empty_rows_run` / `max_empty_cols_run` (sheet scanning guards)

## Testing your package

- Run a quick check with `python -m ade_engine run --config-package <path> --input <file> --output-dir ./output`.
- Keep a small fixture workbook in your repo and add a smoke test that uses `Engine(Settings())` with your package path.
- Use `--log-format ndjson --debug` to capture detector/transform telemetry while iterating.

## Packaging / installation

- The engine accepts either the package directory itself or a project root containing `src/<package>`. `Engine` will adjust `sys.path` accordingly.
- Editable installs work; the engine does not require the package name to be `ade_config`, but that is the default when multiple candidates exist under `src/`.

## Backward compatibility note

Legacy manifest-based wiring is no longer supported. All config logic must be registered explicitly inside `register(registry)` using `registry.register_*`.

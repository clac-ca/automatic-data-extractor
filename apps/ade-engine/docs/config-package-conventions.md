# Config Package Conventions

Config packages supply the domain logic the engine runs. A package is any importable Python package (folder with `__init__.py`) that exposes a `register(registry)` entrypoint.

## Minimal `register` implementation

```python
# src/ade_config/__init__.py
def register(registry):
    # Auto-discover and run register(registry) for any modules under:
    # - ade_config/columns
    # - ade_config/row_detectors
    # - ade_config/hooks
    #
    # The built-in config template ships with this implementation; you can copy it.
    ...
```

Register everything imperatively using `registry.register_*` helpers. Modules can register themselves; `ade_config.register` just imports and invokes them.

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
- Place a `settings.toml` next to your config package (and/or at the project root). A `[ade_engine]` table is recommended to avoid collisions.
- `.env` and `ADE_ENGINE_*` environment variables are also honored.
- Load via `Settings.load(...)`; precedence is documented in `apps/ade-engine/docs/settings.md`.

Commonly overridden settings per package:
- `remove_unmapped_columns` (drop non-canonical columns at write time)
- `write_diagnostics_columns` (include reserved `__ade_*` columns in output)
- `mapping_tie_resolution` (choose `leftmost` vs `leave_unmapped`)
- `detectors.detector_column_sample_size` (column detector sampling policy)
- `max_empty_rows_run` / `max_empty_cols_run` (sheet scanning guards)

## Testing your package

- Run a quick check with `python -m ade_engine process file --config-package <path> --input <file> --output-dir ./output --logs-dir ./logs`.
- Keep a small fixture workbook in your repo and add a smoke test that uses `Engine(Settings())` with your package path.
- Use `--log-format ndjson --debug` to capture detector/transform telemetry while iterating.

## Packaging / installation

- The engine accepts either the package directory itself or a project root containing `src/<package>`.
- Editable installs work; the engine does not require the package name to be `ade_config`, but that is the default when multiple candidates exist under `src/`.

## Backward compatibility note

Legacy manifest-based wiring is no longer supported. All config logic must be registered explicitly inside `register(registry)` using `registry.register_*`.

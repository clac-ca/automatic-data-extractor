# Config packages (registry model)

An ADE **config package** is a regular Python package (commonly named `ade_config`). When the engine runs, it imports your package and calls `register(registry)` to populate the engine registry. No `manifest.toml` is required.

## Minimal layout (recommended)
```text
ade_config/
  __init__.py            # exports register(registry)
  columns/               # one file per canonical field
    email.py
    full_name.py
  row_detectors/         # row detectors
    header.py
    data.py
  hooks/                 # optional lifecycle hooks
    on_table_mapped.py
    on_workbook_before_save.py
```
You can place files anywhere under `ade_config`; the built-in template auto-discovers modules with a `register(registry)` function.

## Plugin types
- **Row detectors** score rows as header/data.
- **Column detectors** score which canonical field a source column represents.
- **Transforms (v3)** return Polars expressions (`pl.Expr`) applied to the table DataFrame.
- **Validators (v3)** return issue-message expressions (null = valid, string = invalid); issues are stored inline in `__ade_issue__*` columns.
- **Hooks** run at lifecycle points; table hooks may replace the DataFrame by returning a new one.

## Settings
Engine settings live outside the config code in `.env`, env vars (`ADE_ENGINE_*`), or optional `settings.toml` (see https://github.com/clac-ca/ade-engine/blob/main/docs/settings.md). Common keys:

- `remove_unmapped_columns`
- `write_diagnostics_columns`
- `mapping_tie_resolution`
- `detector_column_sample_size`

## Output ordering
By default, unmapped columns remain in the output (mapping is rename-only). Reserved `__ade_*` columns are dropped from output unless configured. Custom ordering belongs in `on_table_validated` by returning a reordered DataFrame.

## Adding a field quickly
1. Create `ade_config/columns/my_field.py`.
2. Register the field: `registry.register_field(FieldDef(name="my_field", label="My Field"))`.
3. Add one or more column detectors and register them with `registry.register_column_detector(...)`.
4. Add v3 transforms/validators and register them with `registry.register_column_transform(...)` / `registry.register_column_validator(...)`.

That’s it—no manifest edits. Drop in the file, and discovery picks it up.

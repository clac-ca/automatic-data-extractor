# Config packages (registry model)

An ADE **config package** is a regular Python package named `ade_config`. When the engine runs, it imports every module under this package; decorator side effects register your detectors, transforms, validators, and hooks into the engine registry. No `manifest.toml` is required.

## Minimal layout (recommended)
```text
ade_config/
  __init__.py            # may be empty; import subpackages if you like
  columns/               # one file per canonical field
    email.py
    full_name.py
  rows/                  # row detectors
    header.py
    data.py
  hooks/                 # optional lifecycle hooks
    on_table_mapped.py
    on_workbook_before_save.py
```
You can place files anywhere under `ade_config`; discovery imports everything.

## Plugin types
- **Row detectors** (`@row_detector`) score rows as header/data.
- **Column detectors** (`@column_detector`) score which field a column represents; fields are auto-created on first reference or enriched with `@field_meta`.
- **Column transforms** (`@column_transform` or `@cell_transformer`) return a row-aligned list of values or dicts (can set multiple fields).
- **Column validators** (`@column_validator` or `@cell_validator`) return validation result dicts for reporting only.
- **Hooks** (`@hook(HookName...)`) run at lifecycle points; mutate in place (e.g., reorder columns in `ON_TABLE_MAPPED`).

## Settings
Engine settings live outside the config code in `.env`, env vars (`ADE_ENGINE_*`), or optional `ade_engine.toml` (see `apps/ade-engine/docs/ade-engine/settings.md`). Common keys: `append_unmapped_columns`, `unmapped_prefix`, `mapping_tie_resolution`.

## Output ordering
By default, mapped columns keep input order; unmapped columns append to the right when enabled, prefixed by `unmapped_prefix`. Custom ordering belongs in `ON_TABLE_MAPPED` hooks.

## Adding a field quickly
1. Create `ade_config/columns/my_field.py`.
2. Optionally add `@field_meta(name="my_field", label="My Field")`.
3. Add one or more `@column_detector(field="my_field")` functions.
4. Add `@column_transform` / `@column_validator` as needed.

That’s it—no manifest edits. Drop in the file, and discovery picks it up.

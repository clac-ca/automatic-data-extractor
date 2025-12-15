# ADE Config Package Template (registry-based)

This is a **template ADE config package**. It defines a *target schema* (fields) and the logic the ADE engine uses to:

1. **Detect** tables + header rows (Row Detectors)
2. **Map** spreadsheet columns to canonical fields (Column Detectors)
3. **Normalize** values (Column Transforms)
4. **Report** validation issues (Column Validators)
5. **Customize** the run (Hooks)

## The big idea

- You add Python files wherever you want inside `src/ade_config/`.
- A module becomes a plugin module if (and only if) it defines a top-level `register(registry)`.
- The engine scans the whole package, imports only plugin modules, and calls their `register(registry)` in deterministic module-name order.
- No manifest lists or central file lists—just “create a new module with `register()`”.

## Folder layout (suggested)

```text
src/ade_config/
  columns/                 # one file per canonical field (recommended)
  row_detectors/           # header/data row voting
  hooks/                   # lifecycle hooks
```

> You can restructure freely. Keep registration explicit for clarity/determinism.
>
> Convention: keep auto-discovered modules under `columns/`, `row_detectors/`, and `hooks/`.

## Engine settings (optional)

Engine runtime settings (writer options, thresholds, etc.) can be set via:

- `settings.toml` (recommended for config packages)
- `.env` (works too)
- environment variables

This template includes an example `settings.toml`.

## Adding a new column (canonical field)

1. Copy an existing file in `columns/` (ex: `email.py`)
2. Update the `FIELD = field(...)` metadata
3. Add one or more detector functions and register them via `registry.register_column_detector(...)`.
4. Optionally add transforms/validators and register them via `registry.register_column_transform` / `registry.register_column_validator`.

That’s it.

## Reordering output columns

The engine **preserves input column order** for mapped columns and (optionally) appends unmapped passthrough columns on the right.
If you need a custom order, do it in a hook (see `hooks/on_table_written.py`).

---

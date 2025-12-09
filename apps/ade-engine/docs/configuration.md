# Configuration

`ade-engine` is configured via a **config package** plus CLI/API options.

---

## 1) Config package resolution

The engine accepts a `config_package` reference that can be:

- an importable module name (e.g. `ade_config`)
- a filesystem path to a directory that contains `ade_config/manifest.toml` or `src/ade_config/manifest.toml`

When a filesystem path is provided, the engine prepends the correct parent directory to `sys.path` so `import ade_config` works.

---

## 2) Manifest (`manifest.toml`)

The manifest is validated by Pydantic (`ManifestV1`). It must include:

- `schema` (alias of `schema_id`)
- `version`
- `script_api_version` (must be `3`)
- `[[columns]]` list
- `[writer]` configuration
- optional `[hooks]` configuration

Minimal example:

```toml
schema = "com.example.customer.v1"
version = "1.0.0"
script_api_version = 3

[[columns]]
name = "email"
label = "Email"
required = true
synonyms = ["e-mail", "email_address"]

[[columns]]
name = "first_name"
label = "First name"

[writer]
append_unmapped_columns = true
unmapped_prefix = "raw_"

[hooks]
on_table_mapped = ["table_patch"]  # resolved as ade_config.hooks.table_patch
```

### Fields
Each `[[columns]]` entry supports:

- `name` (canonical field name)
- `label` (human-friendly)
- `module` (optional override module path under config package)
- `required` (bool)
- `synonyms` (list of strings)
- `type` (optional string)

---

## 3) Column modules

For a field `email`, the default module path is:

```
ade_config/column_detectors/email.py
```

A column module may define:

- `detect_*` functions (0..N)
- optional `transform`
- optional `validate`

**Detectors**
- must be callable
- must be keyword-only and accept `**_`
- should return `float` or `dict[str, float]` (optionally wrapped in `{"scores": ...}`)

**Transform**
- signature is keyword-only
- returns a dict of field updates (merged into the row)

**Validate**
- returns a list of issue dicts, e.g.:

```python
return [
  {"code": "missing_email", "severity": "error", "message": "Email is required"},
]
```

---

## 4) Row detectors

Row detectors live under:

```
ade_config/row_detectors/*.py
```

Each module may contain one or more functions named `detect_*`.

Return values:
- `float` (applies to an inferred default label)
- `dict[label, delta]` for explicit labels

Default label inference:
- `__row_label__`, `row_label`, or `default_label`, else
- module name suffix `.header` → label `"header"`
- module name suffix `.data` → label `"data"`

---

## 5) Hooks

Hooks can be defined in `manifest.toml` (preferred) or discovered as a backwards-compatible fallback.

A hook module must expose a callable `run` or `main` entrypoint and accept keyword-only args.

Lifecycle stages:
- `on_workbook_start`
- `on_sheet_start`
- `on_table_detected`
- `on_table_mapped` (may return `ColumnMappingPatch`)
- `on_table_written`
- `on_workbook_before_save`

---

## 6) CLI options (high level)

The CLI exposes:

- `--input` / `--input-dir` (+ `--include` / `--exclude`)
- `--input-sheet` to restrict worksheets
- `--output-dir` (defaults to `./output`, output file names follow `<input>_normalized.xlsx`)
- `--logs-dir` (defaults to `./logs`, log file names follow `<input>_engine.log` or `_engine_events.ndjson`)
- `--log-format` (`text` or `ndjson`)
- `--meta KEY=VALUE` to add run-level metadata to all events
- `--config-package` (module name or path)

The underlying programmatic configuration is `RunRequest`.

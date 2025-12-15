# Settings Reference

`ade_engine.settings.Settings` is a small Pydantic model with an explicit loader: `Settings.load(...)`.

## Load order (lowest → highest precedence)

1) `settings.toml` in the current working directory  
2) `settings.toml` in the config package directory (if available)  
3) `.env` (current working directory)  
4) environment variables prefixed `ADE_ENGINE_`  
5) explicit overrides (kwargs / CLI)

`settings.toml` may use either top-level keys or a nested `[ade_engine]` table.

## Core field

- `config_package: str | None` — optional default config package directory used by the CLI when `--config-package` is omitted. (The engine run itself is driven by `RunRequest.config_package`.)

## Output / writer

- `append_unmapped_columns: bool` — include unmapped source columns in the output (default `True`).
- `render_derived_fields: bool` — include derived (transform-emitted) canonical fields in the output (default `True`).
- `unmapped_prefix: str` — prefix for unmapped headers (default `raw_`; must be non-empty).

## Mapping behavior

- `mapping_tie_resolution: "leftmost" | "leave_unmapped"` — resolve multiple columns mapping to the same field. Default `leftmost`.

## Derived merge behavior

- `derived_write_mode: "fill_missing" | "overwrite" | "skip" | "error_on_conflict"` — how derived field writes behave.
- `missing_values_mode: "none_only" | "none_or_blank"` — how “missingness” is interpreted for merge rules.

## Logging

- `log_format: "text" | "ndjson"` — output format. Default `text`.
- `log_level: int` — standard logging level. Accepts an integer (e.g., `20`) or a level name (e.g., `INFO`, `DEBUG`).

## Scan limits

- `max_empty_rows_run: int | None` — stop scanning a sheet after this many consecutive empty rows (default `1000`; `None` disables).
- `max_empty_cols_run: int | None` — within a row, stop after this many consecutive empty cells beyond the last seen value (default `500`; `None` disables).

## File discovery

- `supported_file_extensions: tuple[str, ...]` — extensions considered when scanning directories for inputs. Default `(".xlsx", ".xlsm", ".csv")`.
  - Can be set in TOML as an array: `[".xlsx", ".csv"]`
  - Can be set via env as a comma-separated string: `ADE_ENGINE_SUPPORTED_FILE_EXTENSIONS=.xlsx,.csv`

## TOML example

```toml
[ade_engine]
append_unmapped_columns = true
unmapped_prefix = "raw_"
mapping_tie_resolution = "leftmost"
log_format = "ndjson"
log_level = "INFO"
max_empty_rows_run = 2000
max_empty_cols_run = 200
supported_file_extensions = [".xlsx", ".csv"]
```


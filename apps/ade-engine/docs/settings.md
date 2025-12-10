# Settings Reference

`ade_engine.settings.Settings` is a `pydantic-settings` model. Values load from (highest precedence first):

1) init kwargs  
2) environment variables prefixed `ADE_ENGINE_`  
3) `.env` file (if present)  
4) `settings.toml` (top-level keys or `[ade_engine]` table)  
5) defaults

## Core fields

- `config_package: str | None` — path to the config package directory. Required by callers; defaults to `None` only so `Settings()` can be instantiated without a path.

## Output / writer

- `append_unmapped_columns: bool` — include unmapped source columns in the output (default `True`).
- `unmapped_prefix: str` — prefix for unmapped headers (default `raw_`; must be non-empty).

## Mapping behavior

- `mapping_tie_resolution: "leftmost" | "leave_unmapped"` — resolve multiple columns mapping to the same field. Default `leftmost`.

## Logging

- `log_format: "text" | "ndjson"` — output format (CLI also accepts `json` as an alias for `ndjson`). Default `text`.
- `log_level: int` — standard logging level (e.g., 10 for DEBUG, 20 for INFO). Defaults to `logging.INFO`.

## Scan limits

- `max_empty_rows_run: int | None` — stop scanning a sheet after this many consecutive empty rows (default `1000`; `None` disables).
- `max_empty_cols_run: int | None` — within a row, stop after this many consecutive empty cells beyond the last seen value (default `500`; `None` disables).

## File discovery

- `supported_file_extensions: tuple[str, ...]` — extensions considered when scanning directories for inputs (case-insensitive). Default `(".xlsx", ".xlsm", ".csv")`.

## TOML example

```toml
[ade_engine]
append_unmapped_columns = true
unmapped_prefix = "raw_"
mapping_tie_resolution = "leftmost"
log_format = "ndjson"
max_empty_rows_run = 2000
max_empty_cols_run = 200
supported_file_extensions = [".xlsx", ".csv"]
```

Place this next to your config package or at the project root. The engine will read either the top-level keys or the `[ade_engine]` table.

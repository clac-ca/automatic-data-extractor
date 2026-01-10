# Settings Reference

`ade_engine.infrastructure.settings.Settings` is a `pydantic-settings` model. You can instantiate it directly (`Settings()`) or use the convenience loader `Settings.load(...)`.

## Load order (lowest → highest precedence)

1) `settings.toml` in the current working directory  
2) `settings.toml` in the config package directory (if available)  
3) `.env` (current working directory)  
4) environment variables prefixed `ADE_ENGINE_`  
5) explicit overrides (kwargs / CLI)

`settings.toml` is flat: keys map 1:1 to `Settings` fields.

## Core field

- `config_package: Path | None` — optional default config package directory used by the CLI when `--config-package` is omitted. (The engine run itself is driven by `RunRequest.config_package`.)

## Output / writer

- `remove_unmapped_columns: bool` — drop non-canonical columns from the written output (default `False`).
- `write_diagnostics_columns: bool` — include engine-reserved `__ade_*` columns in the written output (default `False`).

## Mapping behavior

- `mapping_tie_resolution: "leftmost" | "leave_unmapped"` — resolve multiple columns mapping to the same field. Default `leftmost`.

## Logging

- `log_format: "text" | "ndjson"` — output format. Default `text`.
- `log_level: int` — standard logging level. Accepts an integer (e.g., `20`) or a level name (e.g., `INFO`, `DEBUG`).
- Log files are only written when `--logs-dir` is provided; otherwise logs are emitted to stderr/stdout only.

## Scan limits

- `max_empty_rows_run: int | None` — stop scanning a sheet after this many consecutive empty rows (default `1000`; `None` disables).
- `max_empty_cols_run: int | None` — within a row, stop after this many consecutive empty cells beyond the last seen value (default `500`; `None` disables).

## Detector sampling

These settings control the shared sampling policy used by detectors.
They do not affect transforms or validators, which always process all rows.

- `detector_column_sample_size: int` — max number of values collected into `column_sample_non_empty_values` for each column detector (default `100`).
  - Can be set via env: `ADE_ENGINE_DETECTOR_COLUMN_SAMPLE_SIZE=100`

## Header handling

- `merge_stacked_headers: bool` — merge contiguous header rows into a single header per column (default `true`).
  - Set to `false` to keep each header row as its own table (legacy behavior).
  - Can be set via env: `ADE_ENGINE_MERGE_STACKED_HEADERS=false`

## File discovery

- `supported_file_extensions: tuple[str, ...]` — extensions considered when scanning directories for inputs. Default `(".xlsx", ".xlsm", ".csv")`.
  - Can be set in TOML as an array: `[".xlsx", ".csv"]`
  - Can be set via env as a comma-separated string: `ADE_ENGINE_SUPPORTED_FILE_EXTENSIONS=.xlsx,.csv`

## TOML example

```toml
remove_unmapped_columns = false
write_diagnostics_columns = false
mapping_tie_resolution = "leftmost"
detector_column_sample_size = 100
merge_stacked_headers = true
log_format = "ndjson"
log_level = "INFO"
max_empty_rows_run = 2000
max_empty_cols_run = 200
supported_file_extensions = [".xlsx", ".csv"]
```

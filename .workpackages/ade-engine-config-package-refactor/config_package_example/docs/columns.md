# Columns (canonical fields)

Each module in `src/ade_config/columns/` defines one canonical field:

- `FIELD = field(...)` for metadata
- `@column_detector(FIELD)` functions for header/value scoring
- optional `@column_transform(FIELD)` and `@column_validator(FIELD)`

## Why per-field modules?

It keeps everything about a field in one place:
metadata + detection + normalization + validation.

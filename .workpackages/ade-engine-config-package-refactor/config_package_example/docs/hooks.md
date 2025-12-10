# Hooks

Hooks are optional extension points.

Typical uses:
- add styling / formatting to output workbook
- post-process tables
- call an external model to propose mapping patches

This template includes all common hook stages under `src/ade_config/hooks/`.

## Reordering columns

See `on_table_written.py` for an in-place reorder implementation that:
- reads the written output range into memory
- reorders columns by header name
- writes back to the same range (no insert/delete)

# Pipeline + Registry

This document describes how the pipeline consumes the `Registry` populated by a config package.

## Registry lifecycle

1. **Creation** — the engine creates a fresh `Registry`.
2. **Population** — the engine imports discovered plugin modules and invokes their `register(registry)` functions, which call `registry.register_*` for all fields, detectors, transforms, validators, and hooks.
3. **Finalization** — `registry.finalize()`:
   - sorts callables by `priority` (desc), then module + qualname (deterministic)
   - groups transforms/validators by `field` for fast lookup

## Sheet pipeline steps (high level)

1. **Materialize rows**
   - streams worksheet rows into a trimmed list
   - trims long empty column runs and stops after long empty row runs (settings)

2. **Detect table regions**
   - runs row detectors to classify rows as header/data
   - segments the sheet into one or more table regions

3. **Per-table processing**

For each detected table region:

1. **Extract header + rows**
2. **Materialize a single DataFrame**
   - creates one `pl.DataFrame` for the table data rows
   - uses minimal header normalization to satisfy Polars:
     - empty headers become `col_<i>`
     - duplicates become `<base>__2`, `<base>__3`, ...

3. **Detect + map columns**
   - runs column detectors against the DataFrame (`table`) and active column (`column: pl.Series`)
   - selects at most one source column per registered field (tie resolution is deterministic)

4. **Mapping is rename-only**
   - applies `DataFrame.rename({extracted_name: canonical_field_name})`
   - unmapped columns remain unchanged in the same DataFrame
   - rename collisions are skipped deterministically (with a warning)

5. **Hooks + processing**
   - `on_table_mapped(table=...)` → may return a new DataFrame
   - apply transforms (v3: `Expr` / `dict[str, Expr]`)
   - `on_table_transformed(table=...)` → may return a new DataFrame
   - apply validators (v3: issue-message `Expr`) → writes `__ade_issue__*` columns inline
   - `on_table_validated(table=...)` → may return a new DataFrame

6. **Render**
   - derives `write_table` from `table` by applying:
     - `Settings.remove_unmapped_columns`
     - reserved-column dropping (`__ade_*`) unless `Settings.write_diagnostics_columns`
   - writes `write_table` headers + rows directly to the output worksheet
   - runs `on_table_written(table=write_table, ...)` for formatting/summaries

After `Pipeline.process_sheet` completes, the engine fires `on_sheet_end` with the output
workbook/worksheet for any sheet-level formatting or summaries.

## Logging touchpoints

The pipeline emits structured events when a `RunLogger` is in use, including:

- detector score telemetry (`detector.*`, `row_classification`, `column_classification`)
- transform telemetry (`transform.result`)
- validation telemetry (`validation.summary`)
- write telemetry (`table.written`)

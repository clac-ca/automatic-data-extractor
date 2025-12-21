# Output Ordering

ADE processes each detected table as a single Polars DataFrame. The output worksheet is written directly from that DataFrame (after applying output-column policies).

## Column ordering

- Column order is whatever the pipeline produces:
  - extraction materializes columns in source order (minimal header normalization only)
  - mapping is a rename-only step (no reordering)
  - transforms may add/replace columns
  - hooks may reorder columns by returning a new DataFrame

## Output column policy

At write time, the engine derives `write_table` from the in-memory `table`:

1. If `Settings.remove_unmapped_columns=True`, drop any non-reserved column not in the canonical registry.
2. Drop engine-reserved `__ade_*` columns unless `Settings.write_diagnostics_columns=True`.
3. Write `write_table` headers + rows to the worksheet.

## Row ordering

- Row order is the current DataFrame row order at write time.
- Hooks may filter/sort/reorder rows safely after validation because issues are stored inline as reserved columns.

## Custom ordering

- Use `on_table_validated` to do final shaping (filter/sort/reorder rows; reorder/drop/add columns) by returning a new DataFrame.
- Use `on_table_written` only for formatting/summaries; the `write_table` argument reflects the DataFrame that was written after output-column policies.

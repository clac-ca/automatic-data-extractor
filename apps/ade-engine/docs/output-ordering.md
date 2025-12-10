# Output Ordering

The engine writes a single normalized table per sheet. Column and row ordering follow deterministic rules:

## Columns

1. **Mapped columns**  
   - Ordered by the source column index (i.e., the order they appeared in the input sheet).  
   - If multiple source columns map to the same field, resolution depends on `Settings.mapping_tie_resolution`:
     - `leftmost` (default): keep the highest score; if scores tie, keep the leftmost mapped column and mark the others unmapped.
     - `leave_unmapped`: if more than one column maps to a field, mark all of them unmapped.

2. **Unmapped passthrough columns** (optional)  
   - Appended to the right **after** mapped columns when `Settings.append_unmapped_columns` is `True` (default).
   - Headers use `Settings.unmapped_prefix` (default `raw_`) + the source header value; if the source header is empty, a fallback `col_<index+1>` is used.

## Rows

- The number of data rows written equals the longest column length among mapped + appended unmapped columns. This ensures sheets that have only unmapped columns still emit data rows.
- Header row is always first, followed by data rows in source order.

## Custom ordering

- To enforce a different mapped-column order, patch `table.mapped_columns` in `on_table_mapped` or reorder the output worksheet inside `on_table_written`.
- To suppress passthrough columns entirely, set `append_unmapped_columns=False` via settings or strip them in a hook.

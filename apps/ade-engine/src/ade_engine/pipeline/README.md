# Pipeline overview

## Current limitation: one table per sheet

The pipeline currently processes **exactly one table per worksheet**. `Pipeline.process_sheet`:

- materializes rows, runs `detect_table_bounds()` once, and takes the first header/data region it finds,
- builds a single `TableData` from that region,
- runs hooks/transforms/validators/render once, then returns.

`detect_table_bounds()` treats a table as the header row plus all subsequent rows **until the next detected header or end of data**. However, the pipeline stops after the first table and does not continue scanning for additional tables in the same sheet. Extra tables are effectively ignored once the first table’s end is reached.

## Planned refactor

We intend to extend the pipeline to iterate over sheets and detect **multiple tables per sheet**, using the same definition (header + following rows until the next header or sheet end). That will require looping detection/rendering per table and tracking output placements; this README exists to make the current single-table behavior explicit until that change lands.

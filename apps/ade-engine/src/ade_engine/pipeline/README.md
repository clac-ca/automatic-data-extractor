# Pipeline overview

## Multi-table per sheet

The pipeline processes **multiple tables per worksheet**. `Pipeline.process_sheet`:

- materializes rows once (`Pipeline._materialize_rows`),
- runs `detect_table_regions()` to segment the sheet into table regions,
- processes each table region independently (hooks → mapping → transforms → validators → render),
- renders tables sequentially into the same output worksheet, inserting a blank row between tables.

## Table definition

`detect_table_regions()` treats a table as the header row plus all subsequent rows **until the next detected header or end of data**. Header rows come from the row detector classifier; if a data row appears before any header, the row above is treated as an inferred header (unless that row is empty, in which case the current row is treated as the header).

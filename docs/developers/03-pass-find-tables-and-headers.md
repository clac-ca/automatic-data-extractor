# Pass 1 — Find Tables & Headers (Row Detection)

ADE scans each sheet row by row to decide where tabular data begins and ends and which row should be treated as the header.

## What it reads
- Sheet row stream (no buffering of the full file)
- Config package `rules.row_types.*`
- Prior artifact state for `sheets[]` (if resuming a partial job)

## What it appends (artifact)
- `sheets[].row_classification[]`
- `sheets[].tables[]` with header row A1 ranges and bounds

## Why it matters
Accurate table bounds and header text feed directly into column mapping in the next pass. Without a confident header row, downstream passes cannot map columns to target fields or write a stable normalized workbook.

## See also
- [Job orchestration guide](./02-job-orchestration.md)
- [Pass 2 — Map columns](./04-pass-map-columns-to-target-fields.md)

---

Previous: [Job orchestration guide](./02-job-orchestration.md)  
Next: [Pass 2 — Map columns](./04-pass-map-columns-to-target-fields.md)

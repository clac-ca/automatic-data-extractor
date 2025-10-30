# Pass 4 — Validate Values (Optional)

Validation rules confirm that transformed values meet expectations. Failures are written to the artifact with exact cell ranges so downstream systems (and humans) can fix the issue quickly.

## What it reads
- `tables[].transform[]` (per-column outputs from pass 3)
- Config package validation hooks (`rules.validate.*`)
- Table metadata (header rows, target fields, ranges)

## What it appends (artifact)
- `tables[].validate[]` diagnostics with `{path, level, code, message}`
- `summary.validation` rollups
- `pass_history[]` entry with counts by severity

## Diagnostic shape
Validation traces follow the standard `{ "path": "...", "level": "warning|error", "code": "column.member_id.missing", "message": "Member ID is required" }` shape.

## Common rules
- Required field checks (`validate.required`)
- Format checks (dates, IDs, enumerations)
- Cross-field checks (e.g., start/end date ordering)

## Workflow
1. Pass 3 produces normalized field values.
2. Validation hooks receive each value and return diagnostics or `None`.
3. ADE attaches diagnostics to `tables[].validate[]` and increments counters.

## What to read next
Generate the final workbook in [07-pass-generate-normalized-workbook.md](./07-pass-generate-normalized-workbook.md).

---

Previous: [05-pass-transform-values.md](./05-pass-transform-values.md)  
Next: [07-pass-generate-normalized-workbook.md](./07-pass-generate-normalized-workbook.md)

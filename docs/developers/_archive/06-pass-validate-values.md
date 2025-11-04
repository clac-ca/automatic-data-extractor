# Pass 4 — Validate Values (Optional)

Validation rules confirm that transformed values meet expectations. Failures are written to the artifact with exact cell ranges so downstream systems (and humans) can fix the issue quickly.

## What it reads
- `tables[].transform[]` (per-column outputs from pass 3)
- Config package validation hooks (`rules.validate.*`)
- Table metadata (header rows, target fields, ranges)

## What it appends (artifact)
- `sheets[].tables[].validation.issues[]` with `{row_index, a1, target_field, code, severity, message, rule}`
- `sheets[].tables[].validation.summary_by_field` rollups
- `pass_history[]` entry with counts by severity

## Diagnostic shape
Validation traces normalize common codes (for example, `missing` → `required_missing`) and attach A1 coordinates. Return dictionaries shaped like `{ "row_index": 1, "code": "required_missing", "severity": "error", "message": "Member ID is required" }`.

Recommended codes: `required_missing`, `pattern_mismatch`, `invalid_format`, `out_of_range`, `duplicate_value`. Use them consistently so dashboards can group related issues.

> Note: Validators may still return issues even when there are no data rows; ADE computes the A1 location relative to the header row.

## Common rules
- Required field checks (`validate.required`)
- Format checks (dates, IDs, enumerations)
- Cross-field checks (e.g., start/end date ordering)

## Workflow
1. Pass 3 produces normalized field values.
2. Validation hooks receive each value and return diagnostics or `None`.
3. ADE attaches diagnostics to `tables[].validate[]` and increments counters.

## What to read next
Generate the final workbook in the [Pass 5 guide](./07-pass-generate-normalized-workbook.md).

---

Previous: [Pass 3 — Transform values](./05-pass-transform-values.md)  
Next: [Pass 5 — Generate normalized workbook](./07-pass-generate-normalized-workbook.md)

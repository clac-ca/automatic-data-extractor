# Pass 5 — Generate Normalized Workbook

ADE writes a new sheet with stable headers and column ordering derived from the target field mappings. Optional unmapped columns are appended with the `raw_` prefix.

## What it reads
- `tables[].target_fields[]` and `tables[].mapping[]`
- Config package writer settings (`append_unmapped_columns`, `unmapped_prefix`)
- Transform and validation summaries from earlier passes

## What it appends (artifact)
- `output.normalized_workbook` metadata
- `pass_history[]` entry summarizing rows written and whether unmapped columns were appended
- Updated `summary` rollups (row/column counts, issue totals)

## Why it matters
This pass produces the durable deliverable that downstream systems consume. By streaming rows while writing, ADE keeps memory usage low but still produces a repeatable, auditable output.

## See also
- [Pass 2 — Map columns](./04-pass-map-columns-to-target-fields.md)
- [Pass 3 — Transform values](./05-pass-transform-values.md)
- [Pass 4 — Validate values](./06-pass-validate-values.md)

---

Previous: [Pass 4 — Validate values](./06-pass-validate-values.md)  
Next: [Examples & recipes](./10-examples-and-recipes.md)

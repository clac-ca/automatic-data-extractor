## docs/developers/03-pass-find-tables-and-headers.md

# Pass 1 — Find Tables & Headers (Row Detection)

ADE scans each worksheet to locate tabular regions and choose a header row. Detectors contribute score deltas per row; the highest‑scoring “header” row becomes the table header.

## What it reads

* XLSX workbook opened in **read‑only** mode.
* Config package row detectors under `row_types/*.py` (functions named `detect_*`).
* `manifest.json` (for context only; detection is schema‑agnostic).

## What it appends (artifact)

* `sheets[].row_classification[]` — per‑row label scores with traces:

  * `row_index`, `label` (`header` | `data` | `other`), `confidence` (max score),
  * `scores_by_type` (sum of detector deltas), and `rule_traces[]` ( `{rule, delta}` ).
  * **Rule IDs** are recorded as `<module_id>:<callable>`, e.g. `row_types.header:detect_text_density`.
* `sheets[].tables[]` — one table per sheet (current behavior):

  * `id` (e.g., `Employees-table-1`)
  * `range` (A1 bounds from header row through the last observed row)
  * `data_range` (A1 from first data row; may be `null` if no data)
  * `header` → `{ kind: "raw", row_index, source_header[] }`
  * `columns[]` → `{ column_id: "<table-id>.col.<n>", source_header, order }`
  * `mapping`, `transforms`, `validation` are initialized for later passes

A `pass_history[]` entry named **`structure`** is added with stats:
`{ tables, rows, columns }`.

## Detector contract (row_types)

Row detector functions receive a small, explicit context and return deltas:

```python
# row_types/header.py
def detect_text_density(*, row_index, row_values_sample, sheet_name, source_file, manifest, env, artifact, **_):
    # Return numeric deltas keyed by label(s) you want to influence
    # Keep deltas roughly in [-1.0, +1.0]
    score = min(1.0, sum(bool(v) for v in row_values_sample) / max(1, len(row_values_sample)))
    return {"scores": {"header": score, "data": -0.1}}
```

**Notes**

* ADE aggregates all deltas per label; the label with the highest total becomes `label` for that row and its total becomes `confidence`.
* The chosen header row is the row with the highest `header` score across the sheet.
* Only **header text** and computed **ranges** are persisted; raw cell data is not.

## Why it matters

Accurate header choice and bounds make column mapping deterministic and auditable in Pass 2, and anchor A1 locations for later transforms and validations.

## See also

* [Job orchestration](./02-job-orchestration.md)
* [Pass 2 — Map columns](./04-pass-map-columns-to-target-fields.md)
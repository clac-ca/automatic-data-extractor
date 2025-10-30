# Jobs — Multi‑Pass Pipeline (Artifact v1.1)

A [job](./glossary.md) turns an input file into a normalized spreadsheet using the active [config](./glossary.md). The flow is simple and explainable: detect tables (rows), map **raw columns → target fields** (columns), and generate a normalized workbook while applying **transform** and **validate** inline. One **artifact JSON** is created at job start and enriched across passes.

> **At a glance**
>
> - **Pass 1**: find tables (row detection via `row_types/*`)
> - **Pass 2**: detect & map raw → target using small samples
> - **Pass 2.5 (opt.)**: tiny per‑field stats for sanity checks
> - **Pass 3–4 (inline)**: transform & validate as rows are written
> - **Pass 5**: generate normalized workbook + summary

````

Input file
├─ Pass 1: Row detection (find tables, capture source header)
├─ Pass 2: Column detection & mapping (sample values; raw → target)
├─ Pass 2.5: Analyze (tiny stats; optional)
└─ Pass 3–5: Generate (row-streaming) = transform + validate + write

````

---

## Before you begin

- Ensure exactly one **active** [config](./glossary.md) is set for the target [workspace](./glossary.md).
- Skim the [Glossary](./glossary.md) for **source header**, **target field**, **output header**, and **mapping**.
- Large files are fine: the writer streams **row by row**; transforms/validations run on each value as it is written.

---

## Pass 1 — Row detection (finding tables)

ADE streams rows one by one and applies **row‑type rules** from `row_types/*.py`. Each `detect_*` returns a **delta** for its row type; ADE aggregates deltas into `scores_by_type` and assigns the label with the highest score (tiebreak by manifest order).

**Typical signals**

- Header‑like: high text ratio, header tokens, config synonyms
- Data‑like: numeric density, date/money/id patterns
- Separator‑like: mostly blanks

**Artifact enrichment (excerpt)**

```json
{
  "sheets": [
    {
      "id": "sheet_1",
      "name": "Employees",
      "row_classification": [
        {
          "row_index": 4,
          "label": "header",
          "confidence": 0.91,
          "scores_by_type": { "header": 1.24, "data": 0.11, "separator": -0.10 },
          "rule_traces": [
            { "rule": "row.header.text_density",  "delta": 0.62 },
            { "rule": "row.header.synonym_hits",  "delta": 0.28 }
          ]
        }
      ],
      "tables": [
        {
          "id": "table_1",
          "range": "B4:G159",
          "data_range": "B5:G159",
          "header": {
            "kind": "raw",
            "row_index": 4,
            "source_header": ["Employee ID", "Name", "Department", "Start Date"]
          },
          "columns": [
            { "column_id": "col_1", "source_header": "Employee ID" },
            { "column_id": "col_2", "source_header": "Name" },
            { "column_id": "col_3", "source_header": "Department" }
          ]
        }
      ]
    }
  ],
  "pass_history": [
    { "pass": 1, "name": "structure", "completed_at": "..." }
  ]
}
```

> **No header?** Promote the preceding row if data is seen first; otherwise synthesize `["Column 1", ...]` and mark `header.kind = "synthetic"`.

---

## Pass 2 — Column detection & mapping

ADE samples each **raw column** (`col_1…`) and runs `columns/<field>.py` `detect_*` functions. Each rule returns a **score delta** in favor of **its** field. ADE sums deltas into a score per (raw column, field) and assigns the best field (ties can be left **unmapped**).

**Artifact enrichment (excerpt)**

```json
{
  "sheets": [
    {
      "id": "sheet_1",
      "tables": [
        {
          "id": "table_1",
          "mapping": [
            {
              "raw": { "column": "col_1", "header": "Employee ID" },
              "target_field": "member_id",
              "score": 1.8,
              "contributors": [
                { "rule": "col.member_id.pattern", "delta": 0.90 }
              ]
            },
            {
              "raw": { "column": "col_2", "header": "Name" },
              "target_field": "first_name",
              "score": 1.2
            },
            {
              "raw": { "column": "col_3", "header": "Department" },
              "target_field": "department",
              "score": 0.9,
              "contributors": [
                { "rule": "col.department.synonyms", "delta": 0.60 }
              ]
            }
          ],
          "target_fields": ["member_id", "first_name", "department"]
        }
      ]
    }
  ],
  "pass_history": [
    { "pass": 2, "name": "mapping", "completed_at": "..." }
  ]
}
```

---

## Pass 2.5 — Analyze (optional)

ADE may compute tiny stats (distinct counts, empties, shape hints) to help with sanity checks or tunable thresholds. This is cheap and optional.

```json
{
  "analyze": {
    "member_id":  { "distinct": 155, "empty": 0 },
    "first_name": { "distinct": 142, "empty": 4 }
  }
}
```

---

## Pass 3–5 — Generate (transform + validate + write)

ADE writes a **new workbook** using a **row‑streaming** writer:

1. Build an **output plan** from config `output.order` and the table **mapping**.
2. For each row in the `data_range`:

   * For each **target field** in order:

     * Read the corresponding source cell (via mapping).
     * Apply `transform_value` if defined; otherwise pass through.
     * Apply `validate_value` rules; record issues (no raw values stored).
     * Write the (possibly transformed) value into the output row.
   * If `append_unmapped_columns` is true, write unmapped raw columns as `raw_<source_header>` on the right.
3. Record `transforms[]` summaries and `validation.*` counts in the artifact.

**Artifact enrichment (excerpt)**

```json
{
  "output": {
    "format": "xlsx",
    "sheet": "Normalized",
    "path": "jobs/<job_id>/normalized.xlsx",
    "column_plan": {
      "target": [
        { "field": "member_id",  "output_header": "Member ID",  "order": 1 },
        { "field": "first_name", "output_header": "First Name", "order": 2 },
        { "field": "department", "output_header": "Department", "order": 3 }
      ],
      "appended_unmapped": [
        { "source_header": "Start Date", "output_header": "raw_Start_Date", "order": 4 }
      ]
    }
  },
  "sheets": [
    {
      "id": "sheet_1",
      "tables": [
        {
          "id": "table_1",
          "transforms": [
            { "target_field": "member_id",  "transform": "transform.member_id", "changed": 120, "total": 155 }
          ],
          "validation": {
            "issues": [
              { "a1": "B20", "row_index": 20, "target_field": "member_id", "code": "pattern_mismatch", "severity": "error", "message": "Does not match expected pattern", "rule": "validate.member_id.value" }
            ],
            "summary_by_field": { "member_id": { "errors": 3, "warnings": 1, "missing": 0 } }
          }
        }
      ]
    }
  ],
  "summary": { "rows_written": 155, "columns_written": 4, "issues_found": 4 },
  "pass_history": [
    { "pass": 3, "name": "transform", "completed_at": "..." },
    { "pass": 4, "name": "validate",  "completed_at": "..." },
    { "pass": 5, "name": "generate",  "completed_at": "..." }
  ]
}
```

---

## Outputs & layout

* **Artifact**: `jobs/<job_id>/artifact.json` (the single source of truth)
* **Workbook**: `jobs/<job_id>/normalized.xlsx`

```
jobs/<job_id>/
├─ artifact.json
└─ normalized.xlsx
```

---

## Notes & pitfalls

* Keep detectors **pure and cheap**; row rules run per row, column rules on small samples.
* The **row‑streaming writer** applies transforms and validations per cell while writing; no need to load full sheets.
* A single **active** config per workspace; jobs record the exact config used.
* No plaintext secrets—any secrets in the manifest are decrypted only in sandboxed child processes.

## What’s next

* See config anatomy in [01-config-packages.md](./01-config-packages.md)
* Review script invocation details in [04-runtime-model.md](./04-runtime-model.md)
* Troubleshoot validations in [06-validation-and-diagnostics.md](./06-validation-and-diagnostics.md)
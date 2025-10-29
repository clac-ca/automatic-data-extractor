# ADE — Multi‑Pass Overview (Artifact‑First)

ADE converts messy spreadsheets into a consistent **normalized** Excel output using a streaming, multi‑pass pipeline. It reads **rows** to find tables and header rows, scores **columns** to map them to **target fields**, and then **writes rows** to a new workbook, applying transforms and validations inline (row‑streaming writer).

* **One artifact JSON** is created at job start and **enriched in place** by each pass.
* We use **Excel A1 notation** for cells and ranges (e.g., `"B4"`, `"B4:G159"`).
* Behavior lives in a portable [config](./glossary.md); a [job](./glossary.md) applies one config to one file and records lineage.

---

## Terms (kept obvious and consistent)

* **source header** – the header text found in the input (cleaned/flattened).
* **target field** – the field name defined by the config (formerly “canonical”).
* **output header** – the label written to the normalized output for a target field.
* **raw column** – a physical column in the input table (`col_1`, `col_2`, …).
* **mapping** – assignment from a raw column to a target field with a score.
* **append unmapped** – if true (default), raw columns that didn’t map are appended to the far right as `raw_<sanitized_header>`.

**IDs (stable within a job):**  
`sheets: sheet_1…`, `tables (per sheet): table_1…`, `columns (per table): col_1…`, `rows: 1‑based`.

---

## Excel ranges (A1 notation)

* **Cell**: `"B4"`
* **Range**: `"B4:G159"`
* **Header row index** is numeric (easier for code); **table bounds** keep both A1 and numeric.
* **Data range** is the table range **without** the header row (e.g., `"B5:G159"`).

---

## Artifact JSON — minimal, intuitive shape

The artifact is the single source of truth. It stores **decisions and traces**, not raw cell data.

### Root

```json
{
  "artifact_version": "1.1",
  "job": {
    "job_id": "job_2025-10-29T12-45-00Z_001",
    "source_file": "employees.xlsx",
    "config_id": "cfg_acme_v13",
    "created_at": "2025-10-29T12:45:00Z"
  },
  "engine": {
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
  },
  "rules": {
    "row_types": {
      "row.header.text_density":   { "impl": "row_types/header.py:detect_text_density",   "version": "a1f39d" },
      "row.header.synonym_hits":   { "impl": "row_types/header.py:detect_synonym_hits",   "version": "a1f39d" },
      "row.data.numeric_density":  { "impl": "row_types/data.py:detect_numeric_density",  "version": "b1130d" },
      "row.separator.blank_ratio": { "impl": "row_types/separator.py:detect_blank_ratio", "version": "c22f01" }
    },
    "column_detect": {
      "col.member_id.pattern":     { "impl": "columns/member_id.py:detect_pattern",       "version": "b77bf2" },
      "col.department.synonyms":   { "impl": "columns/department.py:detect_synonyms",     "version": "c1d004" }
    },
    "transform": {
      "transform.member_id":       { "impl": "columns/member_id.py:transform_value",      "version": "d93210" }
    },
    "validate": {
      "validate.member_id.value":  { "impl": "columns/member_id.py:validate_value",       "version": "ee12c3" },
      "validate.required":         { "impl": "columns/_shared.py:validate_required",      "version": "0aa921" }
    }
  },
  "sheets": [],
  "output": null,
  "summary": null,
  "pass_history": []
}
```

**Why this is simple:**

* A **rule registry** at the root (`rules.*`) means traces elsewhere reference **only `rule` IDs** (no duplicate function names).
* The rest is `sheets → tables` with **ranges**, **headers**, **columns**, **mapping**, **transforms**, **validation**.

---

## The same artifact, enriched per pass

Each pass **reads** from earlier sections and **appends** to the same artifact. To keep this light, we include **placeholders** where content is unchanged.

### Pass 1 — Structure (row detection; **row streaming**)

**Reads:** `job`, `engine`, `rules.row_types`
**Appends:** `sheets[].row_classification`, `sheets[].tables[]` with ranges and header

```json
{
  "artifact_version": "1.1",
  "job": { "..." : "..." },
  "engine": { "..." : "..." },
  "rules": { "..." : "..." },

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
            { "rule": "row.header.synonym_hits",  "delta": 0.28 },
            { "rule": "row.data.numeric_density", "delta": -0.05 }
          ]
        }
      ],

      "tables": [
        {
          "id": "table_1",
          "range": "B4:G159",
          "data_range": "B5:G159",

          "header": {
            "kind": "raw",  // "raw" | "synthetic"
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

  "output": null,
  "summary": null,
  "pass_history": [
    { "pass": 1, "name": "structure", "completed_at": "2025-10-29T12:45:07Z" }
  ]
}
```

> **If no header is found:** set `"header.kind": "synthetic"` and use `["Column 1", "Column 2", ...]`.

---

### Pass 2 — Mapping (column detection; **column‑aware via row scans**)

**Reads:** `sheets[].tables[].range/header/columns`, `rules.column_detect`
**Appends:** `sheets[].tables[].mapping[]` and a list of target fields for the output

```json
{
  "artifact_version": "1.1",
  "job": { "..." : "..." },
  "engine": { "..." : "..." },
  "rules": { "..." : "..." },

  "sheets": [
    {
      "id": "sheet_1",
      "name": "Employees",

      "row_classification": [ "..." ],
      "tables": [
        {
          "id": "table_1",
          "range": "B4:G159",
          "data_range": "B5:G159",
          "header": { "..." : "..." },
          "columns": [ "..." ],

          "mapping": [
            {
              "raw": { "column": "col_1", "header": "Employee ID" },
              "target_field": "member_id",
              "score": 1.8,
              "contributors": [
                { "rule": "col.member_id.pattern",  "delta": 0.90 }
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

  "output": null,
  "summary": null,
  "pass_history": [
    { "pass": 1, "name": "structure", "completed_at": "2025-10-29T12:45:07Z" },
    { "pass": 2, "name": "mapping",   "completed_at": "2025-10-29T12:45:12Z" }
  ]
}
```

---

### Pass 2.5 — Analyze (optional tiny stats per field)

**Reads:** `mapping`
**Appends:** `tables[].analyze.{target_field: tiny_stats}`

```json
{
  "sheets": [
    {
      "id": "sheet_1",
      "tables": [
        {
          "id": "table_1",
          "analyze": {
            "member_id":  { "distinct": 155, "empty": 0, "mostly_alnum": true },
            "first_name": { "distinct": 142, "empty": 4, "mostly_lower": true }
          }
        }
      ]
    }
  ],
  "pass_history": [
    { "pass": 2.5, "name": "analyze", "completed_at": "2025-10-29T12:45:15Z" }
  ]
}
```

(If not needed, skip this pass.)

---

### Pass 3 & 4 — Transform and Validate (**inline during generation**)

**Reads:** `mapping`, optional `analyze`, `rules.transform`, `rules.validate`, `engine`
**Appends:** `tables[].transforms[]` and `tables[].validation.*` (no raw data)

```json
{
  "sheets": [
    {
      "id": "sheet_1",
      "tables": [
        {
          "id": "table_1",

          "transforms": [
            { "target_field": "member_id",  "transform": "transform.member_id", "changed": 120, "total": 155, "notes": "uppercased + stripped non-alnum" },
            { "target_field": "first_name", "transform": null,                   "changed": 0,   "total": 155 }
          ],

          "validation": {
            "issues": [
              {
                "a1": "B20",
                "row_index": 20,
                "target_field": "member_id",
                "code": "pattern_mismatch",
                "severity": "error",
                "message": "Does not match expected pattern",
                "rule": "validate.member_id.value"
              }
            ],
            "summary_by_field": {
              "member_id": { "errors": 3, "warnings": 1, "missing": 0 }
            }
          }
        }
      ]
    }
  ],
  "pass_history": [
    { "pass": 3, "name": "transform", "completed_at": "2025-10-29T12:45:22Z" },
    { "pass": 4, "name": "validate",  "completed_at": "2025-10-29T12:45:24Z" }
  ]
}
```

> Implementation detail: both steps occur as cells are written by the **row‑streaming writer**; we still record separate pass markers for clarity.

---

### Pass 5 — Generate (writer‑friendly **row streaming**)

**Reads:** `mapping`, `engine`, optional `analyze`; plus config for output labels/order
**Appends:** `output` (path + plan) and `summary`

```json
{
  "output": {
    "format": "xlsx",
    "sheet": "Normalized",
    "path": "jobs/2025-10-29/normalized.xlsx",

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
  "summary": {
    "rows_written": 155,
    "columns_written": 4,
    "issues_found": 4
  },
  "pass_history": [
    { "pass": 5, "name": "generate", "completed_at": "2025-10-29T12:45:29Z" }
  ]
}
```

---

## Minimal artifact skeleton (quick reference)

```json
{
  "artifact_version": "1.1",
  "job": { "job_id": "...", "source_file": "...", "config_id": "...", "created_at": "..." },
  "engine": { "writer": { "mode": "row_streaming", "append_unmapped_columns": true, "unmapped_prefix": "raw_" } },
  "rules": { "row_types": { }, "column_detect": { }, "transform": { }, "validate": { } },

  "sheets": [
    {
      "id": "sheet_1",
      "name": "Employees",

      "row_classification": [ /* Pass 1 traces */ ],

      "tables": [
        {
          "id": "table_1",

          "range": "B4:G159",
          "data_range": "B5:G159",

          "header": { "kind": "raw", "row_index": 4, "source_header": [ "..." ] },

          "columns": [ { "column_id": "col_1", "source_header": "..." } /* … */ ],

          "mapping": [ /* Pass 2 raw→target with contributors */ ],

          "analyze": { /* Pass 2.5 optional tiny stats */ },

          "transforms": [ /* Pass 3 per-field summaries */ ],

          "validation": { "issues": [/* cell-level */], "summary_by_field": { /* … */ } }
        }
      ]
    }
  ],

  "output": { "format": "xlsx", "sheet": "Normalized", "path": "...", "column_plan": { /* headers+order */ } },
  "summary": { "rows_written": 0, "columns_written": 0, "issues_found": 0 },

  "pass_history": [
    { "pass": 1, "name": "structure", "completed_at": "..." }
    /* passes 2..5 appended over time */
  ]
}
```

**Why this structure is easy to reason about**

* **Familiar Excel ranges** (`"B4:G159"`) and **simple IDs** (`sheet_1/table_1/col_1`) make locations obvious.
* **Source → Target → Output** mirrors what we do: detect what’s there, map to target fields, write normalized output headers.
* **One registry of rules** at the root; everything else references **short `rule` IDs** with numeric `delta`s only when they contributed.
* **Each pass appends** to the same nodes it later reads from (e.g., mapping feeds generation’s `column_plan`).
* **No raw cell data** in the artifact; issues state **where** and **what**, not the value—safer and smaller.
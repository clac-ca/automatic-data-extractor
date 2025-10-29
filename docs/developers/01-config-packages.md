# Config Packages — Behavior as Code (Rows & Columns)

A **config** is a small, portable folder that tells ADE how to read, map, transform, and validate spreadsheets. It defines:

- **Row types** (e.g., `header`, `data`, `separator`, `group_header`) via `row_types/*.py`
- **Target fields** (the normalized schema) via `columns/*.py`
- **Manifest** metadata (engine knobs, field order, output headers)
- Optional **hooks** and local **resources**

ADE loads one config per job, builds a **rule registry** from it, and records that registry into the job’s **artifact JSON**. The artifact then references rules by **stable IDs** (e.g., `row.header.text_density`, `col.member_id.pattern`).

> **At a glance**
>
> - A config is a **folder**: `manifest.json`, `row_types/`, `columns/`, optional `hooks/`, `resources/`.
> - **Row types** mirror columns: one file per type (e.g., `row_types/header.py`), multiple `detect_*` rules inside.
> - **Columns** define detection, transforms, and validation for each **target field**.
> - ADE turns your modules into an `artifact.rules` registry (`rule_id → { impl, version }`).
> - Exactly **one active config** per workspace; only **draft** configs are editable.

---

## Lifecycle

A workspace can hold many configs, but only one is active.

| Status     | Meaning                                    | Editable? | Transitions          |
|------------|--------------------------------------------|-----------|----------------------|
| `draft`    | Being authored; not used by jobs           | Yes       | `active`, `archived` |
| `active`   | Used by current jobs in this workspace     | No        | `archived`           |
| `archived` | Immutable historical record                | No        | (clone → `draft`)    |

**Rules**

- One **active** config per workspace.
- Only **draft** configs are editable.
- Activating a draft archives the previously active config.
- To roll back: **clone** an archived config → edit as draft → activate.

---

## Folder layout (recommended)

```text
my-config/
├─ manifest.json
├─ row_types/
│  ├─ header.py          # detect_* rules that score the "header" row type
│  ├─ data.py            # detect_* rules that score "data"
│  ├─ separator.py       # detect_* rules that score "separator"
│  └─ group_header.py    # (optional) detect_* rules for multi-line or group headers
├─ columns/
│  ├─ member_id.py       # col.* detect rules + transform(_value) + validate(_value)
│  ├─ first_name.py
│  └─ department.py
├─ hooks/                # (optional)
│  ├─ on_job_start.py
│  ├─ after_mapping.py
│  ├─ after_transform.py
│  └─ after_validate.py
└─ resources/            # (optional) dictionaries, patterns, etc.
   └─ synonyms.csv
```

> **Default templates**: Most deployments won’t need to modify `row_types/` often. Ship sane defaults and allow local tweaks by adding or disabling files.

---

## Manifest (schema v1.1)

`manifest.json` describes engine behavior, row types, target fields, and output. All names are **instantly recognizable**:

* **target field** — internal field name for the normalized output (`member_id`)
* **output header** — label written to the output (`Member ID`)
* **synonyms** — header words that boost detection
* **row types** — the set of row classes ADE should score during Pass 1

### Keys

* `info` — schema id, title, version, description
* `engine` — timeouts, memory, header/data thresholds, writer behavior
* `row_types` — enable/disable row type modules; define evaluation order
* `output` — output sheet name and **target field** order
* `fields` — field metadata (label, output header, synonyms, script path, required/enabled)
* `secrets` — encrypted values (if any); decrypted only in sandboxed processes
* `env` — non-sensitive knobs (locale, formats)

### Example (concise)

```json
{
  "info": {
    "schema": "ade.manifest/v1.1",
    "title": "Example Membership Config",
    "version": "1.3.0",
    "description": "Row-type and field rules for member data."
  },

  "engine": {
    "timeout_ms": 120000,
    "memory_mb": 256,
    "header_threshold": 0.8,
    "data_threshold": 0.8,
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
  },

  "row_types": {
    "order": ["header", "group_header", "data", "separator"],
    "meta": {
      "header":      { "enabled": true,  "script": "row_types/header.py" },
      "group_header":{ "enabled": false, "script": "row_types/group_header.py" },
      "data":        { "enabled": true,  "script": "row_types/data.py" },
      "separator":   { "enabled": true,  "script": "row_types/separator.py" }
    }
  },

  "output": {
    "sheet_name": "Normalized",
    "order": ["member_id", "first_name", "department"]
  },

  "fields": {
    "member_id": {
      "label": "Member ID",
      "output_header": "Member ID",
      "required": true,
      "enabled": true,
      "synonyms": ["member id", "member#", "id (member)"],
      "script": "columns/member_id.py"
    },
    "first_name": {
      "label": "First Name",
      "output_header": "First Name",
      "required": true,
      "enabled": true,
      "synonyms": ["first name", "given name"],
      "script": "columns/first_name.py"
    },
    "department": {
      "label": "Department",
      "output_header": "Department",
      "required": false,
      "enabled": true,
      "synonyms": ["dept", "division"],
      "script": "columns/department.py"
    }
  },

  "secrets": {},
  "env": { "LOCALE": "en-CA" }
}
```

> **Order matters**: `row_types.order` informs tiebreaks when scores are equal. `output.order` controls the final column order in the normalized sheet.

---

## How ADE builds `artifact.rules` from your config

On job start ADE:

1. Parses `manifest.json`.
2. Discovers row-type rule functions:

   * For each enabled row type in `row_types.meta`, import the module and collect **every `detect_*`** function.
   * Register each as a rule: `row.<type>.<name>` → `{ impl: "row_types/<file>.py:function", version: <hash> }`.
3. Discovers field rules:

   * From each `fields.<name>.script`, register:

     * `detect_*` → `col.<field>.<name>`
     * `transform_value` / `transform` → `transform.<field>`
     * `validate_value` / `validate` → `validate.<field>.<name>` (or `.value`)

**Result stored in the artifact:**

```json
"rules": {
  "row_types": {
    "row.header.text_density":   { "impl": "row_types/header.py:detect_text_density",   "version": "a1f39d" },
    "row.header.synonym_hits":   { "impl": "row_types/header.py:detect_synonym_hits",   "version": "a1f39d" },
    "row.data.numeric_density":  { "impl": "row_types/data.py:detect_numeric_density",  "version": "b1130d" },
    "row.separator.blank_ratio": { "impl": "row_types/separator.py:detect_blank_ratio", "version": "c22f01" }
  },
  "column_detect": {
    "col.member_id.pattern":     { "impl": "columns/member_id.py:detect_pattern",       "version": "b77bf2" }
  },
  "transform": {
    "transform.member_id":       { "impl": "columns/member_id.py:transform_value",      "version": "d93210" }
  },
  "validate": {
    "validate.member_id.value":  { "impl": "columns/member_id.py:validate_value",       "version": "ee12c3" }
  }
}
```

---

## Script contracts

All functions should be **pure** and **deterministic**. Avoid external I/O unless allowed by `engine`.

### Row‑type rules (`row_types/<type>.py`) — Pass 1

* **Scope**: one whole row’s values (already flattened/cell‑text).
* **Goal**: contribute a **float delta** to the score for *this* row type.
* **Name**: functions start with `detect_`.
* **Return**: `float` (use `0.0` if no contribution). Negative deltas are allowed.

```python
# row_types/header.py
def detect_text_density(*, values: list, **_) -> float:
    non_blank = [v for v in values if v not in (None, "")]
    if not non_blank:
        return 0.0
    text_ratio = sum(isinstance(v, str) for v in non_blank) / len(non_blank)
    return 0.6 if text_ratio >= 0.7 else 0.0

def detect_synonym_hits(*, values: list, field_synonyms: list[str] | None = None, **_) -> float:
    if not field_synonyms:
        return 0.0
    hits = 0
    for v in values:
        if isinstance(v, str) and any(s in v.lower() for s in field_synonyms):
            hits += 1
    return 0.1 * hits
```

> ADE aggregates **per‑type** deltas across all row types, then assigns the label with the highest score (ties broken by `row_types.order`).

### Column detect rules (`columns/<field>.py`) — Pass 2

* **Scope**: a raw column (ADE provides a small `sample` list; keep it cheap).
* **Return**: `float` score delta for **this field**.

```python
# columns/member_id.py
import re
PATTERN = re.compile(r"^[A-Z0-9]{6,32}$")

def detect_pattern(*, header: str | None, sample: list, **_) -> float:
    hits = sum(1 for v in sample if isinstance(v, str) and PATTERN.match((v or "").strip().upper()))
    return 0.2 * hits
```

### Transform — applied during **generation** (row streaming preferred)

```python
def transform_value(v, *, row_index: int, **_):
    if v is None:
        return None
    v = "".join(ch for ch in str(v) if ch.isalnum())
    return v.upper()
```

(If you only provide `transform(values=...)`, ADE may buffer a column.)

### Validate — applied during **generation** (cell‑level issues)

```python
def validate_value(v, *, row_index: int, **_):
    if v is None:
        return [{"code": "required_missing", "severity": "error", "message": "Required value is missing"}]
    if len(str(v)) > 32:
        return [{"code": "too_long", "severity": "error", "message": "Max length is 32"}]
    return []
```

---

## Defaults & extension

* **Default row types**: `header`, `data`, `separator` ship as templates.
* **Extend** by adding files to `row_types/` and listing them in `manifest.row_types.meta` (e.g., `group_header.py`).
* **Disable** a type by setting `"enabled": false`.
* **Priority**: control tie‑break and review focus via `row_types.order`.

---

## Notes & pitfalls

* Keep row‑type rules **cheap**; they run per row in Pass 1.
* Use **synonyms** from field metadata to boost header detection (ADE passes them to row rules).
* Keep `fields` ids in sync with `output.order`.
* Prefer **streaming** `transform_value` / `validate_value` to minimize memory.
* No plaintext secrets; use `manifest.secrets`.

---

## What’s next

* Multi‑pass pipeline & artifact shape: [02-jobs-pipeline.md](./02-jobs-pipeline.md)
* Glossary & terms: [glossary.md](./glossary.md)
* Runtime model (invocation & contexts): [04-runtime-model.md](./04-runtime-model.md)
* Validation & diagnostics: [06-validation-and-diagnostics.md](./06-validation-and-diagnostics.md)

---

## Updated artifact JSON (v1.1) — skeleton with row types

Below is the **minimal skeleton** showing how the new `row_types/` registry and traces appear. We keep A1 ranges, stable IDs, and **no raw data** in the artifact.

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
    "writer": { "mode": "row_streaming", "append_unmapped_columns": true, "unmapped_prefix": "raw_" },
    "header_threshold": 0.8,
    "data_threshold": 0.8
  },

  "rules": {
    "row_types": {
      "row.header.text_density":   { "impl": "row_types/header.py:detect_text_density",   "version": "a1f39d" },
      "row.header.synonym_hits":   { "impl": "row_types/header.py:detect_synonym_hits",   "version": "a1f39d" },
      "row.data.numeric_density":  { "impl": "row_types/data.py:detect_numeric_density",  "version": "b1130d" },
      "row.separator.blank_ratio": { "impl": "row_types/separator.py:detect_blank_ratio", "version": "c22f01" },
      "row.group_header.hyphen":   { "impl": "row_types/group_header.py:detect_hyphen",   "version": "dd09aa" }
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

  "sheets": [
    {
      "id": "sheet_1",
      "name": "Employees",

      "row_classification": [
        {
          "row_index": 4,
          "label": "header",
          "confidence": 0.91,
          "scores_by_type": { "header": 1.24, "group_header": 0.10, "data": 0.11, "separator": -0.10 },
          "rule_traces": [
            { "rule": "row.header.text_density",   "delta": 0.62 },
            { "rule": "row.header.synonym_hits",   "delta": 0.28 },
            { "rule": "row.data.numeric_density",  "delta": -0.05 }
          ]
        }
      ],

      "tables": [
        {
          "id": "table_1",
          "range": "B4:G159",
          "data_range": "B5:G159",

          "header": {
            "kind": "raw",  // or "synthetic" if promoted/synthesized
            "row_index": 4,
            "source_header": ["Employee ID", "Name", "Department", "Start Date"]
          },

          "columns": [
            { "column_id": "col_1", "source_header": "Employee ID" },
            { "column_id": "col_2", "source_header": "Name" },
            { "column_id": "col_3", "source_header": "Department" }
          ],

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

          "analyze": {
            "member_id":  { "distinct": 155, "empty": 0 },
            "first_name": { "distinct": 142, "empty": 4 }
          },

          "transforms": [
            { "target_field": "member_id",  "transform": "transform.member_id", "changed": 120, "total": 155 },
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

  "summary": { "rows_written": 155, "columns_written": 4, "issues_found": 4 },

  "pass_history": [
    { "pass": 1,   "name": "structure", "completed_at": "2025-10-29T12:45:07Z" },
    { "pass": 2,   "name": "mapping",   "completed_at": "2025-10-29T12:45:12Z" },
    { "pass": 2.5, "name": "analyze",   "completed_at": "2025-10-29T12:45:15Z" },
    { "pass": 3,   "name": "transform", "completed_at": "2025-10-29T12:45:22Z" },
    { "pass": 4,   "name": "validate",  "completed_at": "2025-10-29T12:45:24Z" },
    { "pass": 5,   "name": "generate",  "completed_at": "2025-10-29T12:45:29Z" }
  ]
}
```
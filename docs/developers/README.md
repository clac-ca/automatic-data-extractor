# Developer Guide

This guide is the developer entry point for ADE (Automatic Data Extractor). It explains **how ADE works**, **what you configure**, and **where to start** when building or extending behavior.

ADE processes a spreadsheet in a few small steps, each building on the last:

1. **Find tables & headers** — scan rows to locate each table and its header.
2. **Map columns to target fields** — decide what each raw column *is*.
3. **Transform values** *(optional)* — clean/standardize values for each field.
4. **Validate values** *(optional)* — flag issues (required, formats, ranges).
5. **Generate normalized workbook** — write a new sheet with consistent headers and order.

ADE streams data (no full‑sheet loads). Each pass reads from and appends to the same **artifact JSON**, which is your single source of truth for what happened and why.

---

## Quick start (one page)

**Goal:** Detect a *Member ID* column, clean the values, and write a normalized sheet.

1. **Create a config package** (in the UI)
   The UI scaffolds the folder and `manifest.json`. You can export/import as a `.zip`.

2. **Add a column rule**: `columns/member_id.py`

   ```python
   # columns/member_id.py
   def detect_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_):
       score = 0.0
       if header:
           h = header.lower()
           for syn in field_meta.get("synonyms", []):
               if syn in h: score += 0.6
       return {"scores": {field_name: score}}

   def transform(*, values: list, **_):
       def clean(v):
           if v is None: return None
           s = "".join(ch for ch in str(v) if ch.isalnum()).upper()
           return s or None
       return {"values": [clean(v) for v in values], "warnings": []}

   def validate(*, values: list, field_meta: dict, **_):
       issues = []
       if field_meta.get("required", False):
           for i, v in enumerate(values, start=1):
               if not v:
                   issues.append({"row_index": i, "code": "required_missing",
                                  "severity": "error", "message": "Member ID is required."})
       return {"issues": issues}
   ```

3. **Run a job** (upload a workbook in the UI and select your config)
   ADE streams the file, applies your detectors, transforms, and validators, and writes `normalized.xlsx`.

4. **Inspect the artifact** (`artifact.json`)
   You’ll see mapping decisions, rule contributors, and any validation issues.

   ```json
   {
     "artifact_version": "1.1",
     "output": { "format": "xlsx", "sheet": "Normalized", "path": "jobs/<job_id>/normalized.xlsx" },
     "sheets": [{
       "id": "sheet_1",
       "tables": [{
         "id": "table_1",
         "mapping": [
           { "raw": { "column": "col_1", "header": "Employee ID" },
             "target_field": "member_id", "score": 1.8,
             "contributors": [{ "rule": "col.member_id.detect_synonyms", "delta": 0.6 }] }
         ],
         "validation": { "issues": [] }
       }]
     }]
   }
   ```

---

## How ADE runs a file (job orchestration)

ADE performs small, ordered passes. Each pass reads prior decisions and writes new ones to the **artifact JSON**.

```
Input workbook
├─ Pass 1: Find tables & headers (row detection)
├─ Pass 2: Map columns → target fields
├─ Pass 3: Transform values (optional)
├─ Pass 4: Validate values (optional)
└─ Pass 5: Generate normalized workbook (row‑streaming writer)
```

* **Streaming I/O:** ADE reads rows/columns without loading whole sheets into memory.
* **Traceable rules:** The artifact stores rule IDs and score deltas that contributed to decisions.
* **No raw cell data:** Issues record *where* and *what* (with A1 and row indices), not the values.

> For a deeper walkthrough with examples, see **[02‑Job Orchestration](./02-job-orchestration.md)**.

---

## Build behavior with a config package

A **config package** is a portable folder of small, testable Python modules plus a versioned `manifest.json`. You create and edit it in the UI, and you can export/import it as a zip.

```
📁 my-config/
├─ manifest.json                  # engine settings, target fields, script paths
├─ columns/                       # column rules: detect → transform (opt) → validate (opt)
│  ├─ member_id.py
│  ├─ first_name.py
│  └─ department.py
├─ row_types/                     # row rules for Pass 1: finding tables & headers
│  ├─ header.py
│  └─ data.py
├─ hooks/                         # optional: run around job stages
│  ├─ on_job_start.py
│  ├─ after_mapping.py
│  ├─ after_transform.py
│  └─ after_validate.py
└─ resources/                     # optional lookups/dictionaries (no secrets)
```

* **Row rules** help ADE find table bounds and header rows.
* **Column rules** detect, clean, and validate specific **target fields**.
* **Hooks** are extension points with a read‑only view of the **artifact**.

> Full details, contracts, and examples: **[01‑Config Packages — Behavior as Code](./01-config-packages.md)**.

---

## The artifact JSON (at a glance)

ADE creates one **artifact JSON** per job and enriches it throughout the passes. It’s the audit trail and API for what happened.

* **Rules registry** (root) — maps short rule IDs to their script paths and versions.
* **Sheets → tables** — A1 ranges, header info, column mapping, transform/validation summaries.
* **Output + summary** — where the normalized workbook was written and basic stats.

```json
{
  "artifact_version": "1.1",
  "rules": {
    "col.member_id.detect_synonyms": { "impl": "columns/member_id.py:detect_synonyms", "version": "b77bf2" }
  },
  "sheets": [{
    "id": "sheet_1",
    "tables": [{
      "id": "table_1",
      "range": "B4:G159",
      "mapping": [
        { "raw": { "column": "col_1", "header": "Employee ID" },
          "target_field": "member_id", "score": 1.8,
          "contributors": [{ "rule": "col.member_id.detect_synonyms", "delta": 0.6 }] }
      ]
    }]
  }],
  "output": { "format": "xlsx", "sheet": "Normalized", "path": "jobs/<job_id>/normalized.xlsx" }
}
```

> Schemas live under **`./schemas/`**:
> • `artifact.v1.1.schema.json` — authoritative artifact schema
> • `manifest.v0.6.schema.json` — authoritative manifest schema

---

## Testing, safety, and versioning

* **UI‑first editing** with export/import (`.zip`). ADE keeps versions so you can **test**, **publish**, and **roll back**.
* **Validation layers**:

  * L1 (client): Schema and folder checks.
  * L2 (client): Static Python checks (syntax and signatures).
  * L3 (server): Sandboxed import + tiny dry‑runs; builds the rule registry stored in the artifact.
* **Sandboxed runtime** with time/memory limits; no network by default (`allow_net: false`).

---

## Where to go next

1. **[01‑Config Packages — Behavior as Code](./01-config-packages.md)**
   Learn the folder layout, manifest essentials, and full function signatures.

2. **[02‑Job Orchestration — How ADE Runs a File](./02-job-orchestration.md)**
   See the passes end‑to‑end with artifact snippets.

3. **Schemas and templates**

   * **[Artifact schema](./schemas/artifact.v1.1.schema.json)**
   * **[Manifest schema](./schemas/manifest.v0.6.schema.json)**
   * **[Snippet conventions](./templates/snippet-conventions.md)**

4. **Glossary**

   * **[Shared terminology](./glossary.md)** (IDs, ranges, field names, and more)
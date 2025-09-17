# ADE — Automatic Data Extractor

> **From messy spreadsheets/PDFs to clean tables with explainable column mappings.**
> ADE finds **tables** on a page, identifies the **header row**, and maps observed **columns** to canonical **column types** using rule‑based detection with optional value transformation and validation—**with an audit trail for every decision**.

---

## Table of contents

1. [What ADE does](#what-ade-does)
2. [Quick start](#quick-start)
3. [Core concepts (read this first)](#core-concepts-read-this-first)
4. [How it works (at a glance)](#how-it-works-at-a-glance)
5. [Configuration: Snapshots & “Live”](#configuration-snapshots--live)
6. [Data shapes (JSON): Snapshot & Manifest](#data-shapes-json-snapshot--manifest)
7. [Extending ADE (add a column type)](#extending-ade-add-a-column-type)
8. [CLI & Python API](#cli--python-api)
9. [Repository layout](#repository-layout)
10. [Testing](#testing)
11. [Security & PII](#security--pii)
12. [Roadmap](#roadmap)
13. [Contributing](#contributing)
14. [License](#license)

---

## What ADE does

* **Extracts tables** from spreadsheets and table‑like PDF pages.
* **Finds header rows** (per table) by classifying row roles: `header`, `data`, `group_header`, `note`.
* **Maps observed columns → canonical column types** using **detection logic** (boolean functions) with transparent **score/evidence**.
* **Transforms and validates values** (e.g., title‑case names, parse currency, ID checksum).
* **Emits a Manifest**: mappings, confidence, needs‑review flags, and an **audit log** showing which rules/logic fired.
* **Versioned by Snapshots**: one click **Publish Live** / **Rollback**; each run pins the exact `snapshot_id` for reproducibility.

---

## Quick start

> Requires Python 3.11+.

```bash
# 1) Install
pip install -e .

# 2) Run the demo against an example spreadsheet
ade run \
  --document examples/remittance.xlsx \
  --document-type remittance \
  --profile default \
  --use live \
  --out runs/demo-manifest.json

# 3) View results
cat runs/demo-manifest.json
```

**Python (equivalent):**

```python
from ade import run_document

manifest = run_document(
    document="examples/remittance.xlsx",
    document_type="remittance",
    profile="default",
    use="live",  # or a specific snapshot_id
)
print(manifest["pages"][0]["tables"][0]["column_mapping"])
```

---

## Core concepts (read this first)

* **Document Type**: category you’re parsing (e.g., `remittance`, `invoice`).
* **Document → Page → Table**: ADE analyzes each page, splits it into tables, and chooses a **header row** per table.
* **Column (observed)**: a physical column in the table (`header_text`, sampled `values`).
* **Column Type (canonical)**: the **meaning** of a column; defined in a **column catalog**.
* **Detection / Transformation / Validation**: code blocks on a column type.
* **Snapshot**: an **immutable bundle** containing the catalog, column types, schema, header rules, and baked profile overrides.
* **Live pointer**: for each document type (and optionally per profile), indicates which `snapshot_id` is currently Live.
* **Manifest**: run output that **pins** `snapshot_id` and includes mappings + audit.

> Full vocabulary with precise keys is in **[ADE\_GLOSSARY.md](./ADE_GLOSSARY.md)**.

---

## How it works (at a glance)

```mermaid
flowchart TD
  A[Document (XLSX/PDF)] --> B[Pages]
  B --> C[Tables (per page)]
  C --> D[Header Finder]
  D -->|row_type + header_row| C
  C --> E[Columns (Observed)]
  F[Snapshot (Live)] --> G[Column Catalog + Column Types + Schema]
  E --> H[Column Mapper]
  G --> H
  H --> I[Mapping + Confidence + Needs Review + Audit]
  I --> J[Manifest (pins snapshot_id)]
```

---

## Configuration: Snapshots & “Live”

**Why:** Users want *edit → test → publish → rollback* without juggling multiple version numbers.

* **Snapshot**: an immutable, self‑contained config for a `document_type`
  (includes `column_catalog`, all `column_types` with logic, `schema`, `header_finder`, optional baked `profiles`).
* **Live pointer**: maps `document_type` (and optional profile) → `snapshot_id`.
* **Manifest**: pins `snapshot_id` used for the run → deterministic re‑runs.

**Typical GUI flow**

1. Create **Draft** (clone from Live)
2. Edit column types / logic / synonyms / schema
3. Test (corpus impact report)
4. **Publish as Live**
5. Rollback by selecting a previous Snapshot and making it Live

---

## Data shapes (JSON): Snapshot & Manifest

### Snapshot (minimal example)

```json
{
  "snapshot": {
    "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "document_type": "remittance",
    "status": "live",
    "title": "2025-09-17: broaden SIN; name transform fix",
    "created_at": "2025-09-17T14:00:00Z",
    "created_by": "user:justin",

    "column_catalog": [
      "member_first_name", "member_last_name", "government_id",
      "employee_number", "amount_gross", "amount_net", "email"
    ],

    "column_types": {
      "member_first_name": {
        "display_name": "Member First Name",
        "synonyms": ["first name","first_name","firstname","first-name","f name","fname","first*"],
        "detection_logic": {
          "language": "python",
          "entrypoint": "detect",
          "digest": "sha256:9a61…",
          "code": "def detect(header_text, values, **ctx):\n    ht=(header_text or '').lower()\n    for s in ['first name','first_name','firstname','first-name','f name','fname','first']:\n        if s in ht: return True\n    sample=[str(v or '') for v in values[:200]]\n    letters=sum(1 for v in sample if v.replace(' ','').replace('-','').replace(\"'\",'').isalpha())\n    return sample and (letters/len(sample) >= 0.8)\n"
        },
        "transformation_logic": {
          "language": "python",
          "entrypoint": "transform",
          "digest": "sha256:bc88…",
          "code": "def transform(value, **ctx):\n    s=str(value or '').strip().lower()\n    return ' '.join(w.capitalize() for w in s.split())\n"
        },
        "validation_logic": {
          "language": "python",
          "entrypoint": "validate",
          "digest": "sha256:1f2e…",
          "code": "import re\n\ndef validate(value, **ctx):\n    s=str(value or '').strip()\n    return bool(re.match(r\"^[A-Za-z][A-Za-z '\\-]*$\", s))\n"
        }
      }
    },

    "schema": {
      "required_column_types": ["government_id","amount_gross"],
      "optional_column_types": ["member_first_name","member_last_name","employee_number","amount_net","email"],
      "constraints": { "government_id": {"unique": true}, "amount_gross": {"min": 0} }
    },

    "header_finder": {
      "rules": [
        {
          "name": "has_header_words",
          "language": "python",
          "entrypoint": "run",
          "digest": "sha256:ab12…",
          "code": "def run(row_cells, **ctx):\n    WORDS={'employee','sin','gross','net','email'}\n    text=' '.join(str(c or '').lower() for c in row_cells)\n    return any(w in text for w in WORDS)\n"
        }
      ],
      "decision": {
        "row_types": ["header","data","group_header","note"],
        "scoring": "boolean-additive",
        "tie_breaker": "unknown->needs_review"
      }
    }
  }
}
```

### Manifest (run output)

```json
{
  "manifest": {
    "run_id": "run_01J8R0XY…",
    "generated_at": "2025-09-17T15:20:00Z",
    "document_type": "remittance",
    "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "profile": "default",
    "document": "ACME_July_2025.xlsx",
    "pages": [
      {
        "index": 0,
        "tables": [
          {
            "header_row": 3,
            "rows": [
              {"index": 1, "row_type": "note"},
              {"index": 3, "row_type": "header"},
              {"index": 4, "row_type": "data"}
            ],
            "columns": [
              {"index": 0, "header_text": "Emp #"},
              {"index": 1, "header_text": "First Name"},
              {"index": 2, "header_text": "SIN"},
              {"index": 3, "header_text": "Gross $"}
            ],
            "column_mapping": [
              {
                "column_index": 1,
                "column_type": "member_first_name",
                "confidence": 0.96,
                "needs_review": false,
                "score_vector": {"member_first_name": 9, "member_last_name": -3, "email": -2},
                "audit_log": [
                  "synonym match: 'first name'",
                  "value heuristic: letters_ratio=0.92",
                  "transform: title_case applied",
                  "validate: ok"
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

## Extending ADE (add a column type)

> **Goal:** Teach ADE a new semantic column (e.g., `union_local`)—how to recognize it, clean it, and validate it.

1. **Add to the catalog** (inside a Snapshot):

```json
"column_catalog": ["union_local", "..."]
```

2. **Define the column type**:

```json
"column_types": {
  "union_local": {
    "display_name": "Union Local",
    "synonyms": ["union local","local","local #","local number"],
    "detection_logic": {
      "language": "python",
      "entrypoint": "detect",
      "digest": "sha256:…",
      "code": "def detect(header_text, values, **ctx):\n  ht=(header_text or '').lower()\n  return any(s in ht for s in ['union local','local #','local number','local'])\n"
    },
    "transformation_logic": {
      "language": "python",
      "entrypoint": "transform",
      "digest": "sha256:…",
      "code": "def transform(value, **ctx):\n  s=str(value or '').strip()\n  return s.upper()\n"
    },
    "validation_logic": {
      "language": "python",
      "entrypoint": "validate",
      "digest": "sha256:…",
      "code": "def validate(value, **ctx):\n  s=str(value or '').strip()\n  return len(s) > 0\n"
    }
  }
}
```

3. **Update schema** (if required):

```json
"schema": {
  "required_column_types": ["government_id","amount_gross","union_local"]
}
```

4. **Test & publish**: Run against samples → check diffs → **Publish as Live**.

---

## CLI & Python API

> The exact module/CLI names may differ in your codebase; adapt paths accordingly.

### CLI

```bash
# Run with Live config
ade run \
  --document path/to/file.xlsx \
  --document-type remittance \
  --profile default \
  --use live \
  --out runs/out.json

# Run with a specific Snapshot (canary)
ade run \
  --document path/to/file.xlsx \
  --document-type remittance \
  --use snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V \
  --out runs/out.json

# Show which Snapshot is Live
ade live --document-type remittance
```

### Python

```python
from ade import run_document, set_live_snapshot, get_live_snapshot

# Check what's Live
print(get_live_snapshot("remittance"))

# Run with Live
manifest = run_document("examples/remittance.xlsx", "remittance", "default", use="live")

# Run with a specific snapshot_id
manifest = run_document("examples/remittance.xlsx", "remittance", use="snap_…")
```

---

## Repository layout

```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ snapshots/                 # saved Snapshot JSONs (draft/live/archived)
├─ runs/                      # example Manifest outputs
├─ examples/                  # sample spreadsheets/PDFs
├─ src/ade/
│  ├─ cli.py                  # CLI entry points
│  ├─ core/                   # engine: header finder, column mapper
│  ├─ io/                     # spreadsheet/PDF readers
│  ├─ model/                  # data shapes & validators
│  └─ runtime/                # logic loader, sandbox, caching by digest
└─ tests/
```

---

## Testing

```bash
pytest -q
```

* Add corpus tests that compare **two snapshot\_ids** and show mapping diffs.
* Unit test detection/transform/validation blocks with edge cases (empty cells, punctuation, OCR noise).
* Validate that Manifests always include the `snapshot_id`.

---

## Security & PII

* Treat government IDs, emails, and salary amounts as **sensitive**:

  * Redact or hash values in the **audit log** when exporting outside secure contexts.
  * Keep detection/transform/validation code **pure** (no network, no I/O).
* Sandbox user‑provided logic; enforce time/memory limits.

---

## Roadmap

* Optional ML signals (still surfaced as rules/logic) for tie‑break and suggestions
* PDF table detection enhancements (lattice + stream hybrids)
* Corpus‑level impact reports and rule coverage metrics
* GUI: Snapshot diff viewer; staged rollouts by profile

---

## Contributing

1. Fork and clone.
2. Create a branch: `git switch -c feat/<feature-name>`
3. Add tests (`pytest`).
4. For config changes, include updated **Snapshot JSON** in `snapshots/` and a sample **Manifest** in `runs/`.
5. Open a PR with a clear *before/after* summary (include diffs/impact if logic changed).

---

## License

TBD.

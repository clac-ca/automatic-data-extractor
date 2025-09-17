# ADE — Automatic Data Extractor

> **ADE turns messy spreadsheets and PDF tables into clean, typed data with a full audit trail.**

ADE is an internal tool. We optimise for fast iteration, predictable releases, and easy debugging—*not* internet-scale throughput. When a design trade-off appears, we choose the path that keeps the team productive and the system understandable.

---

## Table of contents

1. [What ADE does](#what-ade-does)
2. [Architecture at a glance](#architecture-at-a-glance)
3. [Quick start](#quick-start)
4. [Operating principles](#operating-principles)
5. [Core concepts](#core-concepts)
6. [Configuration & release flow](#configuration--release-flow)
7. [Data outputs](#data-outputs)
8. [Storage & deployment](#storage--deployment)
9. [Repository layout](#repository-layout)
10. [Testing & QA](#testing--qa)
11. [Security & PII](#security--pii)
12. [Roadmap](#roadmap)
13. [Contributing](#contributing)
14. [License](#license)

---

## What ADE does

ADE focuses on a small set of tasks and does them reliably:

1. **Find tables** inside spreadsheets and PDF-like documents.
2. **Pick the header row** by classifying every row (header, data, group header, note).
3. **Map observed columns to canonical column types** with transparent, rule-based detection logic.
4. **Transform and validate values** (currency parsing, ID checks, capitalisation, etc.).
5. **Emit a manifest** that pins the configuration snapshot and records every decision for audit.

Everything else—configuration management, testing, UI experiments—exists to support those five actions.

---

## Architecture at a glance

```mermaid
flowchart TD
  A[Document (XLSX/PDF)] --> B[Pages]
  B --> C[Tables]
  C --> D[Header Finder]
  D -->|row roles + header row| C
  C --> E[Observed Columns]
  F[Snapshot (Live)] --> G[Catalog + Column Types + Schema]
  E --> H[Column Mapper]
  G --> H
  H --> I[Transforms + Validations]
  I --> J[Manifest (mapping + audit + snapshot_id)]
```

The moving parts stay intentionally few: a document reader, a header finder, a column mapper, and configuration packaged as immutable snapshots.

---

## Quick start

> Requires Python 3.11+.

```bash
# 1. Install ADE in editable mode
pip install -e .

# 2. Run the demo spreadsheet with the Live snapshot
ade run \
  --document examples/remittance.xlsx \
  --document-type remittance \
  --profile default \
  --use live \
  --out runs/demo-manifest.json

# 3. Inspect the manifest
jq '.' runs/demo-manifest.json
```

**Python equivalent**

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

## Operating principles

* **Stay deterministic.** Snapshots pin every rule so re-processing a document yields the same manifest.
* **Prefer SQLite and files.** All configuration, manifests, and audit history live in a single `ade.sqlite` database, optionally backed up to disk.
* **Keep logic pure.** Detection, transformation, and validation functions avoid network and filesystem I/O.
* **Surface decisions.** Every run records scores, audit notes, and a `needs_review` flag when margins get thin.
* **Optimise for the team.** ADE is an internal product; small, understandable code beats elaborate abstractions.

---

## Core concepts

| Concept | Summary |
| ------- | ------- |
| **Document type** | Category being parsed (`remittance`, `invoice`, …). |
| **Document → Page → Table → Column** | Processing pipeline: split into pages, detect tables, choose one header row per table, and capture each physical column. |
| **Column type** | Canonical meaning for a column (`member_first_name`, `gross_amount`). Defined in the column catalog. |
| **Logic blocks** | Pure Python callables attached to column types for detection, transformation, and validation. |
| **Snapshot** | Immutable bundle of configuration: catalog, column types, header finder rules, schema, optional profile overrides. |
| **Live pointer** | Per document type (and optional profile) pointer to the snapshot currently in production. |
| **Manifest** | Run output that references the exact snapshot and records mapping details, confidence, and audit entries. |

See **[ADE_GLOSSARY.md](./ADE_GLOSSARY.md)** for precise identifiers and payload sketches.

---

## Configuration & release flow

ADE keeps configuration simple with one database and three states: draft, live, archived.

1. **Clone** the current snapshot: `ade snapshot clone --from live --document-type remittance`.
2. **Edit** detection logic, synonyms, or schema in the draft snapshot (CLI, JSON export, or a lightweight UI).
3. **Test** against a small labelled corpus: `ade test --snapshot draft_… --documents samples/*.xlsx`.
4. **Publish** by flipping the Live pointer: `ade snapshot publish --snapshot draft_…`.

Publishing is atomic because Live is just a pointer in SQLite. Rolling back means pointing back to the previous snapshot. Every manifest records the `snapshot_id`, so reruns stay reproducible.

---

## Data outputs

**Manifest (run report)**

```json
{
  "run_id": "run_01J8Q…",
  "generated_at": "2025-01-18T04:05:06Z",
  "document_type": "remittance",
  "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
  "profile": "default",
  "document": "examples/remittance.xlsx",
  "pages": [
    {
      "index": 0,
      "tables": [
        {
          "header_row": 2,
          "column_mapping": [
            {
              "column_index": 0,
              "column_type": "member_full_name",
              "confidence": 0.92,
              "needs_review": false,
              "audit_log": ["synonym: member name", "transform: title_case"]
            }
          ]
        }
      ]
    }
  ],
  "stats": {"tables_found": 1, "columns_mapped": 5}
}
```

**Snapshot (configuration bundle)**

Snapshots store the column catalog, logic, schema, and optional profile overrides as JSON inside SQLite. Export/import commands exist for code review and backups. The glossary contains a full schema sketch.

---

## Storage & deployment

* **SQLite first.** Configuration, manifests, and Live pointers live in `./var/ade.sqlite` (configurable via `ADE_DB_PATH`).
* **Documents as files.** ADE reads local files; if retention is required, store them in simple blob storage (filesystem, S3 bucket, etc.).
* **Optional exports.** Snapshots can be exported/imported as JSON for diffing and review.
* **Runtime isolation.** Detection, transformation, and validation functions run inside a restricted interpreter to keep runs deterministic.

This setup supports laptops, CI, and a small shared deployment without extra infrastructure.

---

## Repository layout

```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ examples/                  # Sample documents
├─ runs/                      # Example manifest outputs
├─ snapshots/                 # Optional exported snapshots for review
├─ src/ade/
│  ├─ cli.py                  # CLI entry points
│  ├─ core/                   # Header finder, column mapper, scoring
│  ├─ io/                     # Spreadsheet/PDF readers
│  ├─ model/                  # Data shapes & validators
│  └─ storage/                # SQLite persistence helpers
└─ tests/
```

---

## Testing & QA

```bash
pytest -q
```

Testing guidelines:

* Keep a small regression corpus per document type. Compare manifests when upgrading snapshots.
* Unit-test detection, transformation, and validation logic for tricky cases (blank cells, OCR noise, punctuation, locale quirks).
* Ensure every manifest carries the `snapshot_id` and `needs_review` flag when appropriate.

---

## Security & PII

* Treat government IDs, payroll data, and email addresses as sensitive. Redact or hash them before exporting manifests outside secure environments.
* Keep custom logic pure and deterministic—no network calls, disk writes, or uncontrolled randomness.
* Run logic inside a sandbox with execution time and memory limits to avoid runaway scripts.

---

## Roadmap

* Guided rule authoring (show examples where each column type matched or failed).
* Better PDF table detection (hybrid lattice/stream parsing).
* Impact reports comparing two snapshots across a corpus.
* Lightweight web UI for browsing manifests and publishing snapshots.

---

## Contributing

1. Fork and clone the repository.
2. Create a feature branch: `git switch -c feat/<feature-name>`.
3. Add or update tests (`pytest`).
4. Export any modified snapshots or manifests needed for review.
5. Open a pull request describing the behaviour change and test results.

---

## License

TBD.

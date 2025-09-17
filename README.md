# ADE — Automatic Data Extractor

> **ADE turns messy spreadsheets and PDF tables into clean, typed data with a full audit trail.**

ADE is an internal tool. We optimize for fast iteration, predictable releases, and easy debugging—*not* internet-scale throughput. Simplicity wins when it keeps the team productive.

---

## Table of contents

1. [Why ADE exists](#why-ade-exists)
2. [System overview](#system-overview)
3. [Quick start](#quick-start)
4. [Core ideas](#core-ideas)
5. [Configuration & versioning](#configuration--versioning)
6. [Data produced by ADE](#data-produced-by-ade)
7. [CLI & Python API](#cli--python-api)
8. [Storage & deployment model](#storage--deployment-model)
9. [Repository layout](#repository-layout)
10. [Testing](#testing)
11. [Security & PII](#security--pii)
12. [Roadmap](#roadmap)
13. [Contributing](#contributing)
14. [License](#license)

---

## Why ADE exists

ADE does five things reliably:

1. **Finds tables** in spreadsheets and PDF-like documents.
2. **Locates the header row** by classifying each row as header, data, group header, or note.
3. **Maps observed columns to canonical column types** using transparent, rule-based detection logic.
4. **Transforms and validates values** (currency parsing, ID checks, capitalization, etc.).
5. **Emits a manifest** that pins the configuration snapshot and records every decision for auditing.

Everything else—configuration management, testing, GUI ideas—supports those five actions.

---

## System overview

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

The moving parts are intentionally few: a document reader, a header finder, a column mapper, and configuration packaged as immutable snapshots.

---

## Quick start

> Requires Python 3.11+.

```bash
# 1) Install ADE in editable mode
pip install -e .

# 2) Run the demo spreadsheet with the Live snapshot
ade run \
  --document examples/remittance.xlsx \
  --document-type remittance \
  --profile default \
  --use live \
  --out runs/demo-manifest.json

# 3) Inspect the manifest
cat runs/demo-manifest.json | jq '.'
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

## Core ideas

* **Document type** – Category you are parsing (e.g., `remittance`, `invoice`).
* **Document → Page → Table → Column** – ADE processes each page, identifies tables, picks one header row per table, and captures each physical column.
* **Column type** – The canonical meaning of a column (`member_first_name`, `gross_amount`, etc.) defined in the column catalog.
* **Detection / transformation / validation logic** – Pure Python callables attached to column types. They decide matches, normalize values, and flag issues.
* **Snapshot** – Immutable bundle of everything needed to run (catalog, column types, header finder, schema, optional profile overrides).
* **Live pointer** – For each document type (and optional profile) we track which snapshot is currently Live.
* **Manifest** – Run output that references the exact snapshot and records mapping details, confidence, and an audit trail.

See **[ADE_GLOSSARY.md](./ADE_GLOSSARY.md)** for precise definitions, keys, and data shapes.

---

## Configuration & versioning

ADE keeps configuration simple by using three states and one storage technology.

1. **SQLite for everything.** Snapshots, Live pointers, and manifests live in a single `ade.sqlite` file by default. SQLite gives us transactions, history, and easy backups without operating a database cluster.
2. **Snapshots are immutable.** Editing a configuration means cloning the current Live snapshot into a draft, tweaking it, testing, and publishing the draft.
3. **Live is just a pointer.** Publishing swaps the pointer to the new snapshot atomically. Rolling back is another pointer update.

Typical flow:

1. `ade snapshot clone --from live --document-type remittance`
2. Edit column logic, synonyms, or schema in the draft snapshot (via CLI, JSON, or GUI).
3. `ade test --snapshot draft_… --documents samples/*.xlsx` to verify impact.
4. `ade snapshot publish --snapshot draft_…` to move the Live pointer.

Every run writes the `snapshot_id` into its manifest, so reprocessing with the same snapshot produces identical mappings.

---

## Data produced by ADE

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
          "rows": [{"index": 1, "row_type": "group_header"}, …],
          "columns": [{"index": 0, "header_text": "Member Name"}, …],
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

Snapshots hold the column catalog, logic, schema, and optional profile overrides. They are JSON documents persisted in SQLite, exposed through the CLI and API. See the glossary for a full schema sketch.

---

## CLI & Python API

> Command names may evolve; treat these as reference patterns.

### CLI

```bash
# Run a document with the Live snapshot
ade run \
  --document path/to/file.xlsx \
  --document-type remittance \
  --profile default \
  --use live \
  --out runs/out.json

# Run with an explicit snapshot (canary test)
ade run \
  --document path/to/file.xlsx \
  --document-type remittance \
  --use snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V \
  --out runs/out.json

# Show which snapshot is Live
ade live --document-type remittance
```

### Python

```python
from ade import run_document, get_live_snapshot, set_live_snapshot

print(get_live_snapshot("remittance"))

manifest = run_document(
    document="examples/remittance.xlsx",
    document_type="remittance",
    profile="default",
    use="live",
)

# Update the Live pointer (guarded by policy/permissions in production)
set_live_snapshot(document_type="remittance", snapshot_id="snap_…")
```

---

## Storage & deployment model

* **SQLite** backs configuration and run history. The default path is `./var/ade.sqlite`, configurable via `ADE_DB_PATH`.
* **Blob storage** (local filesystem or object store) keeps uploaded documents if retention is required. ADE itself only needs the path during processing.
* **Snapshots as files** remain useful for code review. The CLI can export/import snapshots to JSON for diffing.
* **Runtime isolation**: detection, transformation, and validation functions run inside a restricted interpreter (no network or file I/O) to keep runs deterministic.

This setup supports local development, CI, and a small shared deployment without additional infrastructure.

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

## Testing

```bash
pytest -q
```

Testing guidelines:

* Keep a small regression corpus per document type. Compare manifests when upgrading snapshots.
* Unit-test detection, transformation, and validation logic for tricky cases (blank cells, OCR noise, punctuation, locale quirks).
* Ensure every manifest carries the `snapshot_id` and `needs_review` flag where appropriate.

---

## Security & PII

* Treat government IDs, payroll data, and email addresses as sensitive. Redact or hash them before exporting manifests outside secure environments.
* Keep custom logic pure and deterministic—no network calls, disk writes, or random seeds without control.
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

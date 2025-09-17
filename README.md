# ADE — Automatic Data Extractor

> **ADE turns messy spreadsheets and PDFs into clean, typed data with an audit trail you can trust.**

ADE is an internal tool. We care about shipping features quickly, understanding every decision the system makes, and keeping the
operations footprint tiny. When a design trade-off shows up, we pick the option that keeps the team productive and the platform
predictable.

---

## Table of contents

1. [What ADE delivers](#what-ade-delivers)
2. [System shape](#system-shape)
3. [Quick start](#quick-start)
4. [Operating principles](#operating-principles)
5. [Document flow](#document-flow)
6. [Configuration & release workflow](#configuration--release-workflow)
7. [Data outputs](#data-outputs)
8. [Storage & deployment](#storage--deployment)
9. [Repository layout](#repository-layout)
10. [Testing & QA](#testing--qa)
11. [Security & PII](#security--pii)
12. [Roadmap](#roadmap)
13. [Contributing](#contributing)
14. [License](#license)

---

## What ADE delivers

ADE stays focused on a handful of outcomes:

* **Extract tables** from spreadsheets and PDF-like documents.
* **Detect header rows** by classifying each row (header, data, group header, note).
* **Map observed columns to canonical column types** with simple, rule-first logic.
* **Transform and validate values** (currency parsing, identifier checks, normalisation).
* **Record a manifest** that pins the configuration snapshot and captures the reasoning used.

Everything else—configuration, UI, testing—exists to make those five steps reliable and repeatable.

---

## System shape

ADE ships as a single Docker image that contains both the API backend and the configuration UI. The backend exposes FastAPI
routes; the frontend talks to those routes and anything the UI can do is also available programmatically.

```mermaid
flowchart TB
  subgraph Docker container
    direction TB
    FE[Frontend (Vite + TypeScript)] -->|REST / WebSocket| API[FastAPI backend]
    API --> Worker[Processing engine]
    API -->|SQL| DB[(SQLite ade.sqlite)]
    Worker -->|reads / writes| DB
    Worker --> Files[(Document storage)]
  end
  User --> FE
  Script[Automation / CLI] -->|REST| API
```

### Component responsibilities

| Component | Summary |
| --- | --- |
| **Frontend** | Manage document types, edit detection logic, trigger test runs, publish snapshots, upload documents. |
| **FastAPI backend** | Stateless API for configuration CRUD, run orchestration, manifest retrieval, and document uploads. |
| **Processing engine** | Pure-Python logic for table finding, column mapping, transformations, and validations. |
| **SQLite (`ade.sqlite`)** | Source of truth for snapshots, live pointers, manifests, and audit logs. |
| **Document storage** | Simple file system path mounted into the container (`./var/documents` by default). |

The architecture is intentionally small: one container, one database file, pure functions for business logic.

---

## Quick start

### Prerequisites

* Docker 24+
* Python 3.11+ if running outside Docker

### Run the full stack

```bash
docker compose up --build
```

* Frontend served at <http://localhost:5173> (default Vite dev port).
* API served at <http://localhost:8000>. The OpenAPI docs live at `/docs`.
* SQLite database stored in `./var/ade.sqlite` (relative to the repository).

### Run just the backend for scripting

```bash
pip install -e .
uvicorn ade.app:app --reload --port 8000
```

Then call the same routes the frontend uses:

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -F document_type=remittance \
  -F profile=default \
  -F document=@examples/remittance.xlsx
```

---

## Operating principles

* **Prefer determinism.** Every run ties back to an immutable snapshot.
* **SQLite before services.** Configuration and manifests live in a single database file that ships with the container.
* **Pure logic.** Detection and transformation code avoids network or filesystem side effects.
* **Everything is inspectable.** Manifests include scores, audit notes, and a `needs_review` flag when the margins are thin.
* **APIs first.** The frontend is optional; any action can be triggered via REST.

---

## Document flow

1. **Upload or select a document.** Files are stored on disk and referenced by path.
2. **Split into pages.** Worksheets or PDF pages are processed independently.
3. **Find tables.** The engine detects contiguous cell regions.
4. **Choose a header row.** Row classification finds the header that defines the columns.
5. **Map columns.** Observed columns are scored against column types defined in the snapshot.
6. **Transform and validate values.** Column-specific logic normalises and checks the data.
7. **Emit a manifest.** The manifest records mappings, scores, audit notes, and the snapshot used.

A typical run finishes in a few seconds and writes both the manifest JSON and a summary row to SQLite.

---

## Configuration & release workflow

1. **Clone a snapshot.** Draft a new snapshot from the live baseline for a document type.
2. **Edit logic.** Use the UI or API to tweak synonyms, thresholds, and Python callables.
3. **Test against a corpus.** Upload labelled documents and compare manifests.
4. **Review diffs.** Snapshots can be exported to JSON for code review.
5. **Publish.** Point the `live` pointer to the approved snapshot. The update is transactional.
6. **Archive old snapshots** once they are no longer referenced.

Live behaviour is just a pointer move; historical manifests always reference their original snapshot ID.

---

## Data outputs

### Manifest (run report)

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

### Snapshot (configuration bundle)

Snapshots store the column catalog, logic, schema, and optional profile overrides as JSON inside SQLite. Export and import
commands exist for review and backups. See `ADE_GLOSSARY.md` for the full schema sketch.

---

## Storage & deployment

* **SQLite first.** Everything lives in `./var/ade.sqlite`. Backups are simple file copies.
* **Documents on disk.** The container mounts `./var/documents` for uploads. Swap in S3 or another blob store if needed.
* **Stateless API.** FastAPI instances can scale horizontally by sharing the same SQLite file over a network filesystem if ever
  required, but the default deployment is a single container.
* **Config exports.** Snapshots can be exported as JSON to support pull-request style reviews.

This design runs on laptops, CI, or a small VM with no extra services.

---

## Repository layout

```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ backend/
│  ├─ app/
│  │  ├─ main.py                # FastAPI app
│  │  ├─ routes/                # API routers (runs, snapshots, documents)
│  │  ├─ services/              # Orchestration + SQLite access
│  │  └─ schemas/               # Pydantic models
│  ├─ processor/                # Header finder, column mapper, logic execution
│  └─ tests/
├─ frontend/
│  ├─ src/
│  │  ├─ pages/                 # React/Vue/Svelte pages (config editor, test runner)
│  │  ├─ components/
│  │  └─ api/                   # Thin wrappers over REST endpoints
│  └─ tests/
├─ infra/
│  ├─ Dockerfile
│  └─ docker-compose.yaml
├─ examples/                    # Sample documents
├─ runs/                        # Example manifest outputs
└─ var/
   └─ ade.sqlite                # Local development database (gitignored)
```

Adjust paths as the implementation evolves; the guiding idea is that backend, frontend, and infra live side-by-side.

---

## Testing & QA

```bash
pytest -q                # Backend tests
npm test                 # Frontend unit tests (if applicable)
```

Guidelines:

* Keep a regression corpus per document type and compare manifests during snapshot changes.
* Unit test detection, transformation, and validation logic for edge cases (blank rows, OCR noise, locale quirks).
* Exercise API routes through integration tests to ensure manifests are recorded and audit logs persist.
* Lint and type-check both codebases (`ruff`, `mypy`, `eslint`, `tsc`) to catch issues early.

---

## Security & PII

* Treat government IDs, payroll data, and email addresses as sensitive. Redact or hash before sharing manifests externally.
* Keep custom logic deterministic—no network calls, disk writes, or uncontrolled randomness.
* Run processing inside a sandbox with execution time and memory limits to avoid runaway scripts.
* Restrict document storage folders and the SQLite file to trusted users.

---

## Roadmap

* Guided rule authoring that shows example matches and failures.
* Hybrid lattice/stream PDF detection to improve table discovery.
* Snapshot comparison reports highlighting behavioural changes across corpora.
* UI support for bulk uploads and asynchronous processing queues.

---

## Contributing

1. Fork and clone the repository.
2. Create a feature branch (`git switch -c feat/<feature>`).
3. Add or update tests (`pytest`, `npm test`).
4. Export any modified snapshots or manifests needed for review.
5. Open a pull request summarising the behaviour change and test results.

---

## License

TBD.

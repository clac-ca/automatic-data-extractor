# ADE — Automatic Data Extractor

> **ADE turns semi-structured spreadsheets and PDFs into clean, typed data with an audit trail you can trust.**

ADE is an internal tool. We optimise for transparency, short feedback loops, and ease of operation over internet-scale
optimisation. When we must choose, we pick the option that keeps the system understandable.

---

## Table of contents

1. [What ADE delivers](#what-ade-delivers)
2. [Architecture](#architecture)
3. [Document lifecycle](#document-lifecycle)
4. [Configuration & release flow](#configuration--release-flow)
5. [Data storage](#data-storage)
6. [Getting started](#getting-started)
7. [API primer](#api-primer)
8. [Operating principles](#operating-principles)
9. [Repository layout](#repository-layout)
10. [Testing & QA](#testing--qa)
11. [Security & PII](#security--pii)
12. [Roadmap](#roadmap)
13. [Contributing](#contributing)
14. [License](#license)

---

## What ADE delivers

ADE focuses on a narrow set of outcomes:

* **Extract tables** from spreadsheets or PDF-style documents.
* **Detect header rows** by classifying each row (header, data, group header, note).
* **Map observed columns to canonical column types** using rule-first logic.
* **Transform and validate values** (currency parsing, identifier checks, normalisation).
* **Record a manifest** that pins the configuration snapshot and captures the reasoning used.

Everything else—configuration, UI, testing—exists to make these steps predictable and repeatable.

---

## Architecture

ADE ships as a single Docker image that bundles the frontend and the FastAPI backend. The backend exposes RESTful routes;
anything achievable in the UI can also be driven programmatically.

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
| **Frontend** | Configure document types, edit detection logic, run tests, publish snapshots, upload documents. |
| **FastAPI backend** | Stateless API handling configuration CRUD, run orchestration, manifest retrieval, and uploads. |
| **Processing engine** | Pure-Python logic for table finding, column mapping, transformations, and validations. |
| **SQLite (`ade.sqlite`)** | Source of truth for snapshots, live pointers, manifests, and audit logs. |
| **Document storage** | Simple filesystem path mounted into the container (`./var/documents` by default). |

The target deployment is one container on a small VM or laptop. Horizontal scaling is possible later by reusing the same
SQLite file over a network share, but it is not a design goal.

---

## Document lifecycle

1. **Upload** — Add a document through the UI or POST `/api/v1/documents`. Files land on disk under `var/documents/`.
2. **Select snapshot** — Choose a published snapshot for the document type (defaults to the `live` pointer).
3. **Process** — The processing engine loads the snapshot, extracts tables, maps columns, and runs transforms/validations.
4. **Manifest** — The backend stores the manifest (results, audit log, snapshot ID) in SQLite.
5. **Review** — The UI displays successes, warnings, and any `needs_review` flags; exports provide the same data via JSON.

Manifests are immutable artefacts tied to the snapshot that produced them, so re-running the same snapshot keeps outcomes
repeatable.

---

## Configuration & release flow

* **Draft snapshots** — Create and edit configuration bundles for a document type. Drafts live entirely in SQLite.
* **Testing** — Run example documents against a draft. Compare manifests to prior versions to catch regressions.
* **Publish** — Promote a draft to `live`. Publishing only updates the live pointer; older snapshots remain archived.
* **Profiles** — Optional overrides (extra synonyms, thresholds, context values) scoped to a source or customer. Profiles
  ship with the snapshot and are resolved at run time.
* **Exports** — Snapshots export to JSON for review or backup. Imports create new drafts.

The rule of thumb: never mutate a live snapshot. Create a new draft, test, and publish.

---

## Data storage

ADE keeps persistence simple with a single SQLite database (`ade.sqlite`) and a documents folder.

```sql
CREATE TABLE snapshots (
  snapshot_id     TEXT PRIMARY KEY,
  document_type   TEXT NOT NULL,
  status          TEXT NOT NULL CHECK(status IN ('draft','live','archived')),
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  payload         JSON NOT NULL
);

CREATE TABLE live_registry (
  document_type      TEXT PRIMARY KEY,
  live_snapshot_id   TEXT NOT NULL,
  profile_overrides  JSON DEFAULT NULL,
  updated_at         TEXT NOT NULL,
  updated_by         TEXT NOT NULL
);

CREATE TABLE manifests (
  run_id         TEXT PRIMARY KEY,
  snapshot_id    TEXT NOT NULL,
  document_type  TEXT NOT NULL,
  profile        TEXT,
  generated_at   TEXT NOT NULL,
  document       TEXT NOT NULL,
  payload        JSON NOT NULL
);
```

* **Snapshots** hold catalog, logic, schema, and profile payloads as JSON blobs.
* **Manifests** store run results, including tables, column mappings, stats, and audit logs.
* **Documents** remain on disk. Swap in S3 or another blob store later if required.

---

## Getting started

### Prerequisites

* Docker 24+
* Python 3.11+ (only needed for running the backend outside Docker)
* Node 18+ if you plan to run the frontend dev server separately

### Run the full stack

```bash
docker compose up --build
```

* Frontend: <http://localhost:5173>
* API: <http://localhost:8000> (OpenAPI docs at `/docs`)
* SQLite database: `./var/ade.sqlite`

### Run only the API (for scripting)

```bash
pip install -e .
uvicorn ade.app:app --reload --port 8000
```

The same routes power the UI and CLI tooling.

### Seed documents or snapshots

1. Place example files under `examples/` or `var/documents/`.
2. Use the UI or POST `/api/v1/snapshots/import` with an exported snapshot JSON.
3. Trigger a run via the UI or `POST /api/v1/runs` with `multipart/form-data`.

---

## API primer

Any UI action has a REST counterpart. Example run:

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -F document_type=remittance \
  -F profile=default \
  -F document=@examples/remittance.xlsx
```

Useful endpoints:

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List configured document types and live snapshot IDs. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{id}/publish` | Mark a snapshot as live. |
| `POST /api/v1/runs` | Process a document and create a manifest. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload a document for later runs. |

Refer to `/docs` for the complete OpenAPI schema.

---

## Operating principles

* **Prefer determinism** — Every run references an immutable snapshot ID.
* **SQLite before services** — Configuration, manifests, and audit data stay in a single database file.
* **Pure logic** — Detection and transformation code avoids network or filesystem side effects.
* **Everything is inspectable** — Manifests include scores, audit notes, and `needs_review` flags when margins are thin.
* **APIs first** — The frontend is optional; REST routes are the primary interface.

---

## Repository layout

```text
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
│  │  ├─ pages/                 # Config editor, test runner, manifest viewer
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

Adjust paths as the implementation evolves; keep backend, frontend, and infra side-by-side.

---

## Testing & QA

```bash
pytest -q                # Backend tests
npm test                 # Frontend unit tests
```

Guidelines:

* Maintain a labelled corpus per document type and compare manifests when logic changes.
* Unit test detection, transformation, and validation logic for tricky cases (blank rows, OCR noise, locale quirks).
* Exercise API routes with integration tests to ensure manifests are recorded and audit logs persist.
* Lint and type-check both codebases (`ruff`, `mypy`, `eslint`, `tsc`).

---

## Security & PII

* Treat government IDs, payroll data, and email addresses as sensitive. Redact or hash before sharing manifests externally.
* Run processing in a sandbox with execution time and memory limits to avoid runaway scripts.
* Restrict document storage folders and the SQLite file to trusted users.
* Keep custom logic deterministic—no network calls, disk writes, or uncontrolled randomness.

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

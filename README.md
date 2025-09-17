# ADE — Automatic Data Extractor

> **ADE turns semi-structured spreadsheets and PDFs into trustworthy, typed data while keeping every decision auditable.**

ADE is an internal product. We optimise for clarity, short feedback loops, and easy operations over internet-scale concerns. If a choice trades a little flexibility for simplicity, we take the simple option.

---

## ADE in a minute

* Convert XLSX, CSV, and PDF documents into structured tables.
* Detect headers, map observed columns to a well-defined catalogue, and normalise values.
* Keep every run reproducible through immutable configuration snapshots and stored manifests.
* Provide both a web UI and FastAPI routes—anything you do in the UI can be scripted.

---

## Architecture at a glance

ADE ships as a single Docker image bundling the FastAPI backend and the frontend. One container on a small VM, laptop, or CI worker is the default deployment target.

```mermaid
flowchart LR
  subgraph Docker container
    FE[Frontend (Vite + TypeScript)] -->|REST/WebSocket| API[FastAPI application]
    API --> DB[(SQLite: var/ade.sqlite)]
    API --> Engine[Processing engine]
    Engine --> Files[(Document storage: var/documents)]
  end
  User --> FE
  Script[Automation / CI] -->|REST| API
```

### Component responsibilities

| Component | Summary |
| --- | --- |
| **Frontend** | Configure document types, edit logic, run tests, publish snapshots, upload documents, and compare results across snapshots. |
| **FastAPI backend** | Stateless API surface that handles configuration CRUD, run orchestration, manifest retrieval, and file uploads. |
| **Processing engine** | Pure-Python module that reads a snapshot, finds tables, maps columns, and executes transforms/validations. |
| **SQLite (`var/ade.sqlite`)** | Single source of truth for snapshots, live pointers, manifests, and audit logs. |
| **Document storage (`var/documents/`)** | Filesystem directory mounted into the container for uploaded and example files. |

Horizontal scaling is not a design goal. When capacity becomes a concern we can move SQLite behind a lightweight service, but the baseline deployment stays intentionally simple.

---

## Core concepts

| Term | What it means |
| --- | --- |
| **Document type** | A family of inputs that share the same logic (e.g., payroll remittance). |
| **Snapshot** | Immutable configuration bundle for a document type. Drafts can be edited; live/archived ones are read-only. |
| **Profile** | Optional overrides inside a snapshot that tailor behaviour for a source, customer, or locale. |
| **Manifest** | Stored result of processing a document: detected tables, mappings, audit notes, and the snapshot ID used. |
| **Live pointer** | Record in SQLite that maps a document type (and optional profile) to the snapshot to run in production. |

---

## Document processing flow

1. **Upload** documents via the UI or `POST /api/v1/documents`. Files land under `var/documents/`.
2. **Choose snapshots** to evaluate. The UI supports selecting the live pointer or any historical version. Multiple snapshots can be run against the same uploads to compare behaviour.
3. **Process** by triggering the run in the UI or calling `POST /api/v1/runs`. The processing engine loads the snapshot, extracts tables, maps columns, applies transforms, and validates values.
4. **Review** manifests. Results, warnings, and `needs_review` flags are stored in SQLite and displayed in the UI. JSON manifests are accessible via `GET /api/v1/manifests/{run_id}`.

Re-running the same snapshot on the same file produces identical output. Comparing manifests from different snapshots makes it easy to spot regressions before publishing.

---

## Snapshot workflow

1. **Create a draft** snapshot for a document type. Drafts live entirely inside SQLite.
2. **Iterate and test** by uploading example documents and running them against the draft. The UI highlights diffs against prior manifests so you can inspect behaviour changes.
3. **Publish** once the draft behaves as expected. Publishing only flips the live pointer; older snapshots stay archived for audit or rollback.
4. **Promote profiles** as part of the snapshot. Profile-specific overrides travel with the snapshot, avoiding hidden configuration.

Always create a new draft instead of editing a live snapshot. Snapshots are write-once, guaranteeing reproducibility.

---

## Storage model

ADE keeps persistence intentionally straightforward:

* **SQLite** — Everything lives in one file (`var/ade.sqlite`): snapshots, manifests, live pointers, and audit logs. JSON blobs store snapshot and manifest payloads so schema changes rarely require migrations.
* **File storage** — Uploaded documents, example inputs, and exports are plain files under `var/documents/` (mounted volume in Docker).

Example schema fragment for reference:

```sql
CREATE TABLE snapshots (
  snapshot_id     TEXT PRIMARY KEY,
  document_type   TEXT NOT NULL,
  status          TEXT NOT NULL CHECK(status IN ('draft','live','archived')),
  created_at      TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  payload         JSON NOT NULL
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

Backups are as simple as copying the SQLite file and the documents directory.

---

## API & UI parity

The FastAPI application exposes every operation performed in the UI. Common routes:

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List configured document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process a document (new upload or existing file) and record a manifest. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload a document for later runs. |

OpenAPI docs live at `/docs`, making it easy to script or integrate with other systems.

---

## Local development

* **Docker** — `docker compose up` builds the frontend, backend, and processing engine into one container and mounts `var/` for persistence.
* **Backend** — FastAPI app with Pydantic models, organised into routers (`routes/`), services (`services/`), and the processing engine (`processor/`).
* **Frontend** — Vite + TypeScript app for managing configuration, running comparisons, and inspecting manifests.

During development you can run the backend and frontend separately, but the supported deployment path is the combined container.

---

## Testing & quality

```bash
pytest -q          # Backend tests
npm test           # Frontend unit tests
```

Guidelines:

* Maintain a labelled corpus per document type and run it against drafts before publishing.
* Compare manifests between snapshots to surface regressions early.
* Lint and type-check both codebases (`ruff`, `mypy`, `eslint`, `tsc`).

---

## Security & handling of sensitive data

* Treat government IDs, payroll data, and personal information as sensitive; redact or hash before sharing manifests externally.
* Restrict access to the Docker host, document storage directory, and the SQLite file.
* Run custom logic inside a sandbox with CPU and memory limits to avoid runaway scripts.
* Keep processing logic deterministic—no network calls, random seeds, or disk writes during a run.

---

## Repository layout

```text
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ backend/
│  ├─ app/
│  │  ├─ main.py                # FastAPI app entrypoint
│  │  ├─ routes/                # API routers (runs, snapshots, documents)
│  │  ├─ services/              # Orchestration + SQLite access layer
│  │  └─ schemas/               # Pydantic models
│  ├─ processor/                # Header finder, column mapper, value logic
│  └─ tests/
├─ frontend/
│  ├─ src/
│  │  ├─ pages/                 # Config editor, snapshot comparison, manifest viewer
│  │  ├─ components/
│  │  └─ api/                   # Thin wrappers over REST endpoints
│  └─ tests/
├─ infra/
│  ├─ Dockerfile
│  └─ docker-compose.yaml
├─ examples/                    # Sample documents used in testing
├─ runs/                        # Example manifest outputs
└─ var/
   ├─ documents/                # Uploaded files (gitignored)
   └─ ade.sqlite                # Local development database (gitignored)
```

---

## Roadmap highlights

* Guided rule authoring that shows example matches and failures.
* Snapshot comparison reports that surface behavioural differences in bulk.
* UI support for bulk uploads and asynchronous processing when we outgrow single-run workflows.

---

## License

TBD.

# ADE — Automatic Data Extractor

> **Turn semi-structured spreadsheets and PDFs into trustworthy tables with repeatable rules.**

ADE is an internal tool built to favour fast iteration, easy debugging, and predictable behaviour over internet-scale concerns.  
When a trade-off appears we choose the path that keeps the system obvious to operate.

---

## What ADE delivers

* Converts XLSX, CSV, and PDF documents into typed tabular data with an auditable manifest.
* Keeps document logic versioned as immutable **snapshots** so every run is reproducible.
* Ships as a single Docker container bundling the FastAPI backend, the processing engine, and the frontend UI.
* Offers complete UI ⇄ API parity: anything the UI can do is also exposed as a REST endpoint.
* Stores everything in SQLite and a `var/documents/` folder—backups are a file copy.

---

## Guiding principles

1. **Snapshots first** – Logic is never edited in place. Draft, test on real files, then publish a new snapshot.
2. **Deterministic runs** – Re-running the same snapshot on the same document always yields the same manifest.
3. **Simple ops** – One container, one SQLite database, one documents directory. No hidden infrastructure.
4. **Human friendly** – Plain language names and predictable UI flows beat clever abstractions.

---

## Container architecture

ADE runs as a single Docker image that can live on a laptop, VM, or CI runner.

```
+------------------ Docker container ------------------+
|  Frontend (Vite + TS)  <-->  FastAPI app  <--> Engine |
|                         |                             |
|                         +--> SQLite (var/ade.sqlite)  |
|                         +--> Files (var/documents/)   |
+------------------------------------------------------+
```

* **Frontend** – Configure document types, edit logic, compare snapshots, upload documents, and inspect manifests.
* **FastAPI backend** – Stateless REST API providing CRUD for logic, run orchestration, manifest retrieval, and uploads.
* **Processing engine** – Python module that loads a snapshot, identifies tables, maps columns, and applies transforms/validation.
* **SQLite** – Authoritative store for users, snapshots, manifests, audit logs, and API keys.
* **Documents folder** – Mounted volume for uploaded files, fixtures, and exports.

SQLite is the default and encouraged store. If capacity ever becomes an issue it can later be swapped for another relational
store, but that is intentionally outside the base design.

---

## Core workflows

### Process documents

1. **Upload** files through the UI or `POST /api/v1/documents`. Files are saved to `var/documents/`.
2. **Choose snapshots** to evaluate. Pick the live pointer or any historical version; selecting multiple snapshots lets you compare outputs.
3. **Run processing** from the UI or `POST /api/v1/runs`. The engine loads the snapshot, extracts tables, maps columns, and applies transformations.
4. **Review manifests** via the UI or `GET /api/v1/manifests/{run_id}`. Compare manifests across snapshots to see behaviour changes before publishing.

### Manage logic

1. **Create a draft snapshot** for a document type. Drafts live in SQLite and stay editable until published.
2. **Iterate and test** by uploading sample files and running them against the draft. The UI highlights diffs against previous manifests.
3. **Publish** when satisfied. Publishing moves the live pointer; the underlying snapshot remains immutable for audit or rollback.
4. **Bundle profiles** (source- or customer-specific overrides) inside the snapshot so no external configuration is required.

### Compare versions

Use the snapshot comparison view to run the same uploads across multiple snapshots—live or historical—and highlight manifest differences. This is the primary way to validate logic changes.

---

## Persistence model

* **SQLite (`var/ade.sqlite`)** – Holds snapshots, manifests, live pointers, audit logs, users, and API keys. Snapshot and manifest payloads are stored as JSON so schema updates rarely require migrations.
* **File storage (`var/documents/`)** – Uploaded documents, fixtures, and exported manifests. Mount this directory as a Docker volume.

Backups consist of copying the SQLite file and the documents directory.

---

## API, UI, and automation

The FastAPI application exposes every operation available in the UI:

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List configured document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process a document (new upload or existing file) and record a manifest. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload a document for later runs. |

OpenAPI docs are served at `/docs`, making scripting and CI integration straightforward. Because the backend is API-first, anything the frontend does can also be automated.

---

## Authentication & access

* **User login** – Username/password authentication is the default. Credentials live in SQLite and are managed through the admin UI.
* **SSO (optional)** – You can plug in an SSO provider (SAML/OIDC) at a single integration point without touching the rest of the stack.
* **Roles** – `viewer`, `editor`, and `admin` roles govern who can edit logic, publish snapshots, or manage users.
* **API keys** – Admins can generate and revoke API keys. Keys map back to a user and inherit that user’s role permissions.

Keep authentication simple: restrict access to the Docker host and treat the SQLite database and documents directory as sensitive assets.

---

## Local development & deployment

* **Docker** – `docker compose up` builds the frontend, backend, and engine into one container and mounts `var/` for persistence.
* **Backend** – FastAPI app with Pydantic models organised into routers (`routes/`), services (`services/`), and the processing engine (`processor/`).
* **Frontend** – Vite + TypeScript app for editing logic, running comparisons, and inspecting manifests.

During development you may run the backend and frontend separately, but production deploys should use the combined container.

---

## Testing & quality

```bash
pytest -q          # Backend tests
ruff check         # Python linting
mypy               # Python type checks
npm test           # Frontend unit tests
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

Guidelines:

* Maintain a labelled corpus per document type and run it against drafts before publishing.
* Compare manifests between snapshots to surface behaviour changes early.
* Keep processing logic deterministic—no network calls, random seeds, or disk writes during a run.

---

## Security considerations

* Treat government IDs, payroll data, and personal information as sensitive; redact or hash before sharing manifests externally.
* Restrict access to the Docker host, document storage directory, and SQLite file.
* Run custom logic inside a sandbox with CPU and memory limits to avoid runaway scripts.

---

## Repository layout

```text
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ backend/
│  ├─ app/
│  │  ├─ main.py                # FastAPI entrypoint
│  │  ├─ routes/                # API routers (runs, snapshots, documents, auth)
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
* Snapshot comparison reports that surface behaviour differences in bulk.
* UI support for bulk uploads and asynchronous processing if single-run workflows become limiting.

---

## License

TBD.

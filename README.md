# ADE — Automatic Data Extractor

> **ADE turns semi-structured spreadsheets and PDFs into trustworthy, typed data with an audit trail you can replay at any time.**

ADE is an internal product and we optimise for quick feedback, predictable behaviour, and easy operations over internet-scale concerns. When a trade-off appears, we pick the option that keeps the system simple for the team that runs it.

---

## ADE at a glance

* Converts XLSX, CSV, and PDF documents into structured tables.
* Keeps business logic versioned as immutable snapshots so every run is reproducible.
* Ships as a single Docker container that bundles the FastAPI backend, the processing engine, and the frontend UI.
* Anything you can do through the UI can also be done through the public API (and therefore through scripts or CI jobs).
* Stores state in SQLite and a documents folder—backups are a file copy.

---

## Product principles

1. **Snapshots first** — Logic is never edited in place. Create a draft, try it against real files, and publish when satisfied.
2. **UI + API parity** — If the UI does it, the API can do it. Automation uses the same primitives as humans.
3. **Deterministic runs** — Rerunning the same snapshot on the same file produces identical manifests.
4. **Simple deploys** — One Docker image, one SQLite database, one documents directory.

---

## System architecture

ADE is delivered as a Docker image you can run on a laptop, a VM, or inside CI.

```
+------------------ Docker container ------------------+
|  Frontend (Vite + TS)  <-->  FastAPI app  <-->  Engine|
|                         |                              |
|                         +--> SQLite (var/ade.sqlite)   |
|                         +--> Documents (var/documents/) |
+-------------------------------------------------------+
```

* **Frontend** – Configure document types, edit logic, manage snapshots, upload documents, and compare manifests.
* **FastAPI backend** – Stateless REST API that handles CRUD, run orchestration, manifest retrieval, and uploads.
* **Processing engine** – Python module that loads a snapshot, finds tables, maps columns, and applies transforms and validations.
* **SQLite (`var/ade.sqlite`)** – Single source of truth for snapshots, live pointers, manifests, and audit logs.
* **Documents (`var/documents/`)** – Filesystem directory mounted into the container for uploads and fixtures.

The default deployment runs one container. If capacity ever becomes a concern, SQLite can be replaced with a lightweight managed service, but that is intentionally out of scope for the base design.

---

## Core workflows

### Processing a document

1. **Upload** documents through the UI or `POST /api/v1/documents`. Files land under `var/documents/`.
2. **Select snapshots** to evaluate. Choose the live pointer or any historical version; compare multiple snapshots against the same uploads.
3. **Process** via the UI or `POST /api/v1/runs`. The engine loads the snapshot, extracts tables, maps columns, runs transforms, and validates values.
4. **Review manifests** in the UI or `GET /api/v1/manifests/{run_id}`. Compare manifests across snapshots to spot regressions before publishing.

### Managing snapshots

1. **Create a draft** for a document type. Drafts live entirely inside SQLite and remain editable.
2. **Iterate and test** by uploading sample files and running them against the draft. The UI surfaces diffs against prior manifests.
3. **Publish** when satisfied. Publishing flips the live pointer; existing snapshots stay archived for audit or rollback.
4. **Bundle profiles** inside the snapshot so source- or customer-specific overrides stay versioned with the logic.

Always create a new draft instead of editing a live snapshot. Snapshots are immutable once published or archived.

### Comparing versions

The UI supports running the same uploads across multiple snapshots (live or historical) and highlighting differences in manifests. This "snapshot comparison" view is the primary way to validate changes before publication.

---

## Persistence model

ADE keeps persistence intentionally straightforward:

* **SQLite** — Everything lives in one file: snapshots, manifests, live pointers, audit logs, user accounts, and API keys. Snapshot and manifest payloads are stored as JSON so schema changes rarely require migrations.
* **File storage** — Uploaded documents, example inputs, and exports are plain files under `var/documents/` (mounted volume in Docker).

Backups are as simple as copying the SQLite file and the documents directory.

---

## API, UI, and automation

The FastAPI application exposes every operation performed in the UI. Common routes include:

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List configured document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process a document (new upload or existing file) and record a manifest. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload a document for later runs. |

OpenAPI docs live at `/docs`, making it easy to script or integrate with other systems. API keys can be generated for automation (see “Authentication & access”).

---

## Authentication & access

* **User login** – Username/password authentication is the default. Credentials live in SQLite and can be managed through the admin UI.
* **SSO (optional)** – Plug in an SSO provider if desired; the FastAPI app exposes a single integration point so you can add SAML/OIDC without touching the rest of the stack.
* **Roles** – Users belong to roles (viewer, editor, admin). Roles govern who can edit logic, publish snapshots, or manage users.
* **API keys** – Admins can mint and revoke API keys. Keys map back to a user and inherit that user’s role permissions.

Keep it simple: no need for elaborate IAM. Restrict access to the Docker host and treat the SQLite database and documents directory as sensitive assets.

---

## Local development & deployment

* **Docker** – `docker compose up` builds the frontend, backend, and engine into one container and mounts `var/` for persistence.
* **Backend** – FastAPI app with Pydantic models, organised into routers (`routes/`), services (`services/`), and the processing engine (`processor/`).
* **Frontend** – Vite + TypeScript app for managing configuration, running comparisons, and inspecting manifests.

During development you can run the backend and frontend separately, but the supported deployment path is the combined container.

---

## Testing & quality

```bash
pytest -q          # Backend tests
npm test           # Frontend unit tests
ruff check         # Python linting
mypy               # Python type checks
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

Guidelines:

* Maintain a labelled corpus per document type and run it against drafts before publishing.
* Compare manifests between snapshots to surface behavioural differences early.
* Keep processing logic deterministic—no network calls, random seeds, or disk writes during a run.

---

## Security considerations

* Treat government IDs, payroll data, and personal information as sensitive; redact or hash before sharing manifests externally.
* Restrict access to the Docker host, document storage directory, and the SQLite file.
* Run custom logic inside a sandbox with CPU and memory limits to avoid runaway scripts.

---

## Repository layout

```text
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ backend/
│  ├─ app/
│  │  ├─ main.py                # FastAPI app entrypoint
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
* Snapshot comparison reports that surface behavioural differences in bulk.
* UI support for bulk uploads and asynchronous processing when we outgrow single-run workflows.

---

## License

TBD.

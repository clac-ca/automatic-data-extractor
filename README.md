# ADE — Automatic Data Extractor

> Turn semi-structured spreadsheets and PDFs into dependable tables with repeatable rules.

ADE is an internal product designed for teams who need to iterate quickly on document extraction without building or maintaining complex infrastructure. Deterministic behaviour, easy debugging, and predictable operations take priority over internet-scale throughput.

---

## Why teams choose ADE

- **Convert documents into typed tables.** XLSX, CSV, and PDF files become structured manifests you can load into downstream systems.
- **Version everything through snapshots.** Each change to detection logic is packaged as an immutable snapshot so every run is reproducible.
- **Ship one container.** A single Docker image bundles the FastAPI backend, the Python processing engine, and the frontend UI.
- **Keep UI and API in sync.** Every UI action is also available through a REST endpoint, making automation straightforward.
- **Rely on simple storage.** SQLite and a `var/documents/` directory hold all persistent data; backups are just file copies.

---

## Core ideas

- **Document type** – A family of related documents that share extraction rules (for example “Payroll Remittance”).
- **Snapshot** – An immutable bundle of logic for a document type. You edit drafts, publish new versions, and keep history forever.
- **Run** – Executing the engine on a document with one or more snapshots to produce manifests.
- **Manifest** – The result of a run: detected tables, column mappings, audit notes, and statistics.
- **Profile** – Optional overrides for a document type (e.g., customer-specific tweaks) stored within a snapshot payload.

---

## How everything is packaged

```
+-------------------- Docker container --------------------+
| Frontend (Vite + TS) <-> FastAPI routes <-> Processing   |
|                                |                         |
|                                +-> SQLite (var/ade.sqlite)
|                                +-> Documents (var/documents/)
+----------------------------------------------------------+
```

- **Frontend** – Configure document types, manage snapshots, run comparisons, upload files, and inspect manifests.
- **FastAPI backend** – Stateless REST API that handles authentication, CRUD for logic, orchestration of runs, and manifest retrieval.
- **Processing engine** – Pure Python module that applies header detection, column mapping, transformations, and validations.
- **SQLite + files** – Authoritative storage for users, snapshots, manifests, API keys, and uploaded documents.

SQLite is the default and recommended database. Swap it out only if your data volume genuinely demands something else.

---

## Everyday workflows

### Process documents

1. Upload one or more files through the UI or `POST /api/v1/documents`. Files land in `var/documents/`.
2. Pick the snapshots to evaluate. Choose the live pointer or any historical version; multiple selections let you compare outputs.
3. Start a run from the UI or `POST /api/v1/runs`. The engine loads each snapshot, extracts tables, maps columns, and applies transformations.
4. Review manifests in the UI or via `GET /api/v1/manifests/{run_id}`. Compare results across snapshots before promoting new logic.

### Iterate on logic

1. Create a draft snapshot for the relevant document type.
2. Edit column catalogues, detection logic, and schema rules in the UI. Drafts stay editable in SQLite until published.
3. Test against real documents. The UI highlights diffs versus previous manifests so you can see exactly what changed.
4. Publish when satisfied. Publishing only moves the live pointer—older snapshots remain immutable for audit and rollback.

### Compare versions in the UI

The snapshot comparison view lets you run the same uploads across multiple snapshots (live or historical) and see manifest differences side by side. Use this workflow before every publication to validate the impact of your changes.

---

## Storage & backups

- **SQLite (`var/ade.sqlite`)** stores snapshots, manifests, live pointers, audit logs, users, and API keys. Snapshot and manifest payloads are JSON blobs to minimise migrations.
- **File storage (`var/documents/`)** keeps uploaded documents, fixtures, and exported manifests. Mount this as a Docker volume.

Backups are a simple copy of the SQLite file plus the documents directory.

---

## API & automation

OpenAPI documentation lives at `/docs`. Every UI action has an API equivalent:

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process uploaded or in-flight documents and record manifests. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload a document for later runs. |

Because the backend is API-first, anything you can do in the UI can also be scripted.

---

## Access control

- **User login** – Username/password authentication by default. Credentials live in SQLite and are manageable through the admin UI.
- **SSO (optional)** – Swap in an SSO provider (SAML or OIDC) behind a single integration point without touching the rest of the stack.
- **Roles** – `viewer`, `editor`, and `admin` govern who can edit logic, publish snapshots, or manage users.
- **API keys** – Admins can issue and revoke keys. Each key maps to a user and inherits that user’s role permissions.

Treat the Docker host, SQLite database, and document directory as sensitive assets.

---

## Deploy & operate

- **Local development** – Run frontend and backend separately if preferred (`uvicorn backend.app.main:app --reload` and `npm run dev`). Both talk to the same SQLite file.
- **Single-container deployment** – `docker compose up` builds the frontend, backend, and engine into one container and mounts `./var` for persistence.
- **Configuration** – Environment variables cover database location, file storage path, and auth providers. Defaults target SQLite and local file storage.
- **Monitoring** – Application logs stream to stdout. Keep an eye on disk usage of `var/` and the number of stored manifests.

---

## Testing & QA

```bash
pytest -q          # Backend tests
ruff check         # Python linting
mypy               # Python type checks
npm test           # Frontend unit tests
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

Keep processing logic deterministic: no network calls, random numbers, or disk writes during a run.

---

## Repository layout

```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ AGENTS.md
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

- Guided rule authoring that shows example matches and failures.
- Snapshot comparison reports that surface behaviour differences at scale.
- UI support for bulk uploads and asynchronous processing if single-run workflows become limiting.

---

## License

TBD.

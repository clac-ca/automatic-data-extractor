# ADE — Automatic Data Extractor

Turn semi-structured spreadsheets and PDFs into reliable tables with rules you can version, test, and publish.

ADE is an internal tool for teams who want dependable extraction logic without operating a fleet of services. Determinism, simple operations, and quick iteration matter more than horizontal scale.

---

## Why ADE

- **Own the logic.** Build document-specific rules, track them as snapshots, and publish on your schedule.
- **Compare before you ship.** Run new snapshots against the same uploads and review manifest diffs in the UI.
- **One deployable unit.** A single Docker container packages the FastAPI backend, Python processing engine, and Vite + TypeScript frontend.
- **Storage you can reason about.** SQLite and a `var/documents/` folder hold everything. Backups are just file copies.
- **API-first by design.** Every UI action corresponds to a REST endpoint, so automation and scripting stay simple.

---

## Architecture snapshot

```
+--------------------- Docker container ---------------------+
| Frontend (Vite + TS) <-> FastAPI routes <-> Processing     |
|                                   |                        |
|                                   +--> SQLite (var/ade.sqlite)
|                                   +--> Documents (var/documents/)
+-------------------------------------------------------------+
```

- **Frontend** – Configure document types, edit logic, manage runs, upload files, and review manifests.
- **FastAPI backend** – Stateless API for authentication, CRUD operations, running jobs, and manifest retrieval.
- **Processing engine** – Pure Python module that performs header detection, column mapping, transformations, and validation.
- **SQLite + files** – Authoritative storage for users, snapshots, manifests, audit trails, and uploaded documents.

SQLite is the default database. Swap it only if data volume outgrows a single file.

---

## Core concepts

- **Document type** – Family of similar documents that share extraction rules (for example, “Payroll Remittance”).
- **Snapshot** – Immutable bundle of logic for a document type. Drafts are editable; published snapshots are frozen.
- **Run** – Execution of one or more snapshots against uploaded documents to produce manifests.
- **Manifest** – Run result that stores detected tables, column mappings, audit notes, and statistics.
- **Profile** – Optional overrides (customer, locale, etc.) stored within a snapshot payload.

---

## Everyday workflows

### Process documents

1. Upload one or more files through the UI or `POST /api/v1/documents`. Files land in `var/documents/`.
2. Select the snapshots to evaluate—use the live pointer or any specific versions. Multiple selections let you compare outputs.
3. Start a run from the UI or `POST /api/v1/runs`. The engine applies each snapshot and records manifests.
4. Review manifests in the UI or via `GET /api/v1/manifests/{run_id}`. Compare snapshots side by side before promoting new logic.

### Iterate on logic

1. Create a draft snapshot for the relevant document type.
2. Edit column catalogues, detection logic, schema rules, and profile overrides in the UI.
3. Test drafts against real uploads. The UI surfaces manifest diffs versus the current live snapshot.
4. Publish when ready. Publishing only advances the live pointer; older snapshots stay immutable for audit and rollback.

### Compare versions in the UI

Select one or more documents plus multiple snapshots (live or historical) and launch a comparison run. The UI highlights manifest differences so you can confirm behavioural changes before shipping.

---

## API and automation

OpenAPI documentation lives at `/docs`. Common endpoints:

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process uploaded documents and store manifests. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload documents for later runs. |

Anything exposed in the frontend can also be automated through the API.

---

## Authentication and roles

- **Username/password** – Default sign-in method. Credentials live in SQLite and are managed through the admin UI.
- **SSO (optional)** – A single integration point supports SAML or OIDC providers if required.
- **Roles** – `viewer`, `editor`, and `admin` govern who can edit logic, publish snapshots, manage users, or issue keys.
- **API keys** – Admins can generate API keys linked to a user. Keys inherit the user’s role permissions.

Treat the Docker host, SQLite database, and documents directory as sensitive assets.

---

## Storage and backups

- **SQLite (`var/ade.sqlite`)** stores snapshots, manifests, live pointers, audit logs, users, sessions, and API keys. Snapshot and manifest payloads are JSON blobs to keep migrations light.
- **File storage (`var/documents/`)** holds uploaded documents, fixtures, and exported manifests. Mount it as a Docker volume in production.

Backups require copying the SQLite file and the documents directory.

---

## Development and deployment

- **Local development** – Run the backend with `uvicorn backend.app.main:app --reload` and the frontend with `npm run dev`. Both target the same SQLite database and documents folder.
- **Single-container deployment** – `docker compose up` builds the combined image and mounts `./var` for persistence.
- **Configuration** – Environment variables cover database paths, document storage, and authentication providers. Defaults point to SQLite and local file storage.
- **Monitoring** – Application logs stream to stdout. Watch disk usage for the `var/` directory and the number of stored manifests.

---

## Testing and quality

```bash
pytest -q          # Backend tests
ruff check         # Python linting
mypy               # Python type checks
npm test           # Frontend unit tests
npm run lint       # Frontend linting
npm run typecheck  # Frontend type checks
```

Processing logic must stay deterministic—avoid network calls, randomness, or disk writes during runs.

---

## Repository layout (planned)

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
│  │  └─ api/                   # REST client wrappers
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

- Guided rule authoring that shows example matches and misses.
- Snapshot comparison reports that surface behaviour differences at scale.
- UI support for bulk uploads and asynchronous processing if single-run workflows become limiting.

---

## License

TBD.

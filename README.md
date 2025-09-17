# ADE — Automatic Data Extractor

ADE is an internal tool that turns semi-structured spreadsheets and PDFs into deterministic tables. We optimise for clarity, reproducibility, and easy operations—the entire platform runs from a single Docker container, a SQLite file, and a documents folder.

---

## Why ADE exists

- **One source of truth** – Author extraction logic once and replay it deterministically whenever documents arrive.
- **Audit confidence** – Snapshots, manifests, and audit logs preserve how and why data landed in the warehouse.
- **Small-team friendly** – Operating ADE means backing up `var/ade.sqlite` and `var/documents/`; no extra services required.

---

## Design commitments

1. **Deterministic processing** – Every manifest ties back to an immutable snapshot with recorded logic digests.
2. **Plain architecture** – FastAPI + SQLite + TypeScript are enough. Add dependencies only when a real need appears.
3. **API-first workflow** – The UI uses the same endpoints exposed to automation, so scripts and humans stay in sync.
4. **Pure extraction logic** – Detection, transformation, and validation code run without side effects to keep reruns repeatable.

---

## System overview

```
+-------------------- Docker container --------------------+
|  Vite + React UI  ↔  FastAPI backend  ↔  Processor layer  |
|                          |                                 |
|                          ├─ SQLite  (var/ade.sqlite)       |
|                          └─ Documents (var/documents/)     |
+-----------------------------------------------------------+
```

- **Frontend** – Configure document types, edit logic, upload files, review manifests, and compare versions.
- **Backend** – FastAPI routes for authentication, CRUD, run orchestration, and manifest retrieval.
- **Processor** – Pure Python helpers that detect tables, map columns, transform values, and collect audit notes.
- **Storage** – SQLite tables and the documents directory cover all persistence. Migrate only if usage outgrows the single-file model.

Snapshots drive every run: they bundle detection logic, schema expectations, and profile overrides. Runs can evaluate several snapshots side by side so reviewers can inspect manifest diffs before promoting new logic.

---

## Core vocabulary

| Term | Plain-language meaning |
| --- | --- |
| **Document type** | Group of documents that share extraction rules (for example, payroll remittances). |
| **Snapshot** | Immutable bundle of logic for a document type. Drafts are editable; published snapshots are read only. |
| **Profile** | Optional overrides (customer, locale, etc.) stored with the snapshot payload. |
| **Run** | Execution of one or more snapshots against uploaded documents. |
| **Manifest** | Structured result of a run: detected tables, column mappings, audit notes, and statistics. |

See `ADE_GLOSSARY.md` for the full data dictionary.

---

## Typical workflows

### Process new documents

1. Upload files via the UI or `POST /api/v1/documents`; uploads persist in `var/documents/`.
2. Choose the snapshots to evaluate (live pointer or historical versions).
3. Start a run from the UI or `POST /api/v1/runs`; the processor applies each snapshot and stores manifests in SQLite.
4. Review manifests in the UI or `GET /api/v1/manifests/{run_id}` before promoting new logic.

### Improve extraction logic

1. Create or copy a draft snapshot for the relevant document type.
2. Update column catalogues, detection rules, schema requirements, and profile overrides.
3. Test drafts against real uploads and inspect manifest diffs versus the live snapshot.
4. Publish when satisfied. Publishing advances the live pointer; previous versions remain immutable for audit and rollback.

### Compare versions in the UI

1. Select documents and the snapshots to evaluate.
2. Trigger a comparison run—each snapshot produces its own manifest.
3. Inspect diffs and audit notes to confirm behaviour before promoting logic.

---

## API starting points

Interactive documentation lives at `/docs`.

| Endpoint | What it does |
| --- | --- |
| `GET /api/v1/document-types` | List document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process uploaded documents and persist manifests. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload documents for later runs. |

All UI actions call these APIs so automation can follow the same paths.

---

## Access model

- **Username/password** – Default sign-in stored in SQLite and managed through the admin UI.
- **Optional SSO** – Add a single SAML or OIDC provider if required by the deployment.
- **Roles** – `viewer`, `editor`, and `admin` control editing, publishing, user management, and API key issuance.
- **API keys** – Admins can create keys tied to specific users; keys inherit the user’s role permissions.

Protect the Docker host, the SQLite database, and the documents directory—they contain everything ADE knows.

---

## Storage and backups

- **SQLite (`var/ade.sqlite`)** stores snapshots, manifests, users, sessions, API keys, and audit metadata. Snapshot and manifest payloads remain JSON to avoid premature schema design.
- **File storage (`var/documents/`)** holds uploads, fixtures, and exported manifests. Mount it as a Docker volume when running in production.

Backing up ADE means copying both locations. Restore them together to recover a deployment.

---

## Development and deployment

- **Local development** – Run the backend with `uvicorn backend.app.main:app --reload` and the frontend with `npm run dev`; both share the same SQLite database and documents folder.
- **Single-container deploy** – `docker compose up` builds the combined image and mounts `./var` for persistence.
- **Configuration** – Environment variables control database paths, storage directories, and authentication providers. Defaults point to SQLite and the local file system.
- **Monitoring** – Logs stream to stdout. Watch the size of `var/` and the number of manifests produced per run.

---

## Repository layout (planned)

```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ AGENTS.md
├─ backend/
│  ├─ app/            # FastAPI entrypoint, routes, schemas, services
│  ├─ processor/      # Header finder, column mapper, value logic
│  └─ tests/
├─ frontend/
│  ├─ src/            # Pages, components, API client wrappers
│  └─ tests/
├─ infra/
│  ├─ Dockerfile
│  └─ docker-compose.yaml
├─ examples/          # Sample documents used in testing
├─ runs/              # Example manifest outputs
└─ var/
   ├─ documents/      # Uploaded files (gitignored)
   └─ ade.sqlite      # Local development database (gitignored)
```

---

## What’s next

- Guided rule authoring that surfaces example matches and misses.
- Snapshot comparison reports that summarise behaviour changes across batches of documents.
- Bulk uploads and, if needed, background processing once single-run workflows become limiting.

---

## License

TBD.

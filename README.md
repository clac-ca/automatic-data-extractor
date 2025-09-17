# ADE — Automatic Data Extractor

ADE converts semi-structured spreadsheets and PDFs into deterministic tables. The product is an internal tool, so our design favours clarity, debuggability, and easy operations over large-scale throughput. SQLite and a simple file store give us everything we need.

---

## Guiding principles

- **Deterministic by default.** All extraction rules are versioned snapshots so you always know which logic created a manifest.
- **One predictable deployment.** Ship ADE as a single Docker image containing the FastAPI backend, Python processing engine, and Vite + TypeScript frontend.
- **Operate with files.** SQLite at `var/ade.sqlite` and uploaded documents under `var/documents/` hold all state. Backups are file copies.
- **APIs back every action.** Anything possible in the UI is available via REST, enabling scripting and automation without extra work.

---

## System overview

```
+--------------------- Docker container ---------------------+
| Frontend (Vite + TS) <-> FastAPI routes <-> Processing     |
|                                   |                        |
|                                   +--> SQLite (var/ade.sqlite)
|                                   +--> Documents (var/documents/)
+-------------------------------------------------------------+
```

- **Frontend** – Configure document types, edit logic, upload files, compare manifests, and review audit details.
- **FastAPI backend** – Stateless routes for authentication, CRUD, job orchestration, and manifest retrieval.
- **Processing engine** – Pure Python functions for header detection, column mapping, transformations, and validation.
- **Storage** – SQLite plus the documents folder store users, snapshots, manifests, audit trails, and uploads. Switch databases only if a single SQLite file stops being practical.

Snapshots drive every run. They package detection logic, schema expectations, and optional profile overrides. Runs can reference one or many snapshots so you can compare outputs inside the UI before promoting new logic.

---

## Core concepts

- **Document type** – Family of documents that share extraction rules (for example, payroll remittances).
- **Snapshot** – Immutable bundle of logic for a document type. Drafts are editable; published snapshots are read-only.
- **Profile** – Optional overrides (customer, locale, etc.) stored inside a snapshot payload.
- **Run** – Execution of one or more snapshots against uploaded documents.
- **Manifest** – Structured result of a run: detected tables, column mappings, audit notes, and statistics.

Refer to `ADE_GLOSSARY.md` for precise field names used across the API and database.

---

## Everyday workflows

### Upload and process documents

1. Upload one or more files through the UI or `POST /api/v1/documents`. Files live in `var/documents/`.
2. Select the snapshots to evaluate—use the live pointer or specific versions. Multiple snapshots allow side-by-side comparisons.
3. Start a run from the UI or `POST /api/v1/runs`. The engine applies each snapshot and records manifests.
4. Review manifests in the UI or via `GET /api/v1/manifests/{run_id}`. Compare results before promoting new logic.

### Improve extraction logic

1. Create a draft snapshot for the relevant document type.
2. Update column catalogues, detection logic, schema rules, and profile overrides in the UI.
3. Test drafts against real uploads and review manifest diffs versus the live snapshot.
4. Publish when satisfied. Publishing advances the live pointer; previous versions stay immutable for audit and rollback.

### Compare versions in the UI

1. Select documents and the snapshots to evaluate (live or historical).
2. Run the comparison. Each snapshot produces its own manifest.
3. Inspect diffs to confirm behaviour changes before promoting logic.

---

## API quick reference

OpenAPI documentation is served at `/docs`.

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/document-types` | List document types and their live snapshots. |
| `POST /api/v1/snapshots` | Create or update a draft snapshot. |
| `POST /api/v1/snapshots/{snapshot_id}/publish` | Promote a snapshot to live. |
| `POST /api/v1/runs` | Process uploaded documents and store manifests. |
| `GET /api/v1/manifests/{run_id}` | Retrieve manifest payloads for auditing. |
| `POST /api/v1/documents` | Upload documents for later runs. |

Every UI action maps to an API route so automation can follow the same flows.

---

## Authentication and access

- **Username/password** – Default sign-in method stored in SQLite and managed in the admin UI.
- **SSO (optional)** – Support a single SAML or OIDC provider if required.
- **Roles** – `viewer`, `editor`, and `admin` determine who can edit logic, publish snapshots, manage users, or issue keys.
- **API keys** – Admins can create API keys tied to a user; keys inherit the user’s role permissions.

Treat the Docker host, SQLite database, and documents directory as sensitive assets.

---

## Storage and backups

- **SQLite (`var/ade.sqlite`)** stores snapshots, manifests, live pointers, users, sessions, and API keys. Snapshot and manifest payloads are JSON blobs to keep migrations simple.
- **File storage (`var/documents/`)** holds uploaded documents, fixtures, and exported manifests. Mount it as a Docker volume in production.

Backups require copying the SQLite file and the documents directory together.

---

## Development and deployment

- **Local development** – Run the backend with `uvicorn backend.app.main:app --reload` and the frontend with `npm run dev`. Both share the SQLite database and documents folder.
- **Single-container deployment** – `docker compose up` builds the combined image and mounts `./var` for persistence.
- **Configuration** – Environment variables cover database paths, document storage, and authentication providers. Defaults point to SQLite and local file storage.
- **Monitoring** – Application logs stream to stdout. Watch `var/` disk usage and manifest volume.

---

## Planned repository map

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

## Roadmap highlights

- Guided rule authoring that surfaces example matches and misses.
- Snapshot comparison reports that summarise behaviour changes across batches of documents.
- UI support for bulk uploads and asynchronous processing if single-run workflows become limiting.

---

## License

TBD.

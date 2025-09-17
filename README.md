# ADE — Automatic Data Extractor

ADE turns semi-structured spreadsheets and PDFs into reliable tables with snapshot-driven rules you control. It is an internal tool, so we optimise for clarity, determinism, and easy operations instead of internet-scale throughput.

---

## Why ADE

- **Own the rules.** Document-specific logic lives in versioned snapshots that you can test and publish on your schedule.
- **See the impact before shipping.** Upload documents, try multiple snapshots (live or historical), and compare manifest diffs in the UI.
- **Ship one container.** A single Docker image bundles the FastAPI backend, Python processing engine, and Vite + TypeScript frontend.
- **Simple persistence.** SQLite (`var/ade.sqlite`) and a documents folder (`var/documents/`) hold all state; backups are file copies.
- **API-first.** Every UI action has a matching REST endpoint, so scripting and integrations stay simple.

---

## System design

```
+--------------------- Docker container ---------------------+
| Frontend (Vite + TS) <-> FastAPI routes <-> Processing     |
|                                   |                        |
|                                   +--> SQLite (var/ade.sqlite)
|                                   +--> Documents (var/documents/)
+-------------------------------------------------------------+
```

- **Frontend** – Configure document types, edit logic, run comparisons, upload files, and review manifests.
- **FastAPI backend** – Stateless routes for authentication, CRUD operations, job orchestration, and manifest retrieval.
- **Processing engine** – Pure Python functions that perform header detection, column mapping, transformations, and validation.
- **Storage** – SQLite plus a documents folder store users, snapshots, manifests, audit trails, and uploads. Swap SQLite only if a single file stops being practical.

Snapshots drive every run: they bundle detection logic, schema expectations, and optional profile overrides. Runs can reference one or many snapshots so you can compare outputs inside the UI.

---

## Core concepts

- **Document type** – Family of documents that share extraction rules (for example, “Payroll Remittance”).
- **Snapshot** – Immutable bundle of logic for a document type. Drafts are editable; published snapshots are read-only.
- **Profile** – Optional overrides (customer, locale, etc.) stored inside a snapshot payload.
- **Run** – Execution of one or more snapshots against uploaded documents to produce manifests.
- **Manifest** – Structured result of a run: detected tables, column mappings, audit notes, and statistics.

---

## Everyday flow

### Upload and process documents

1. Upload one or more files through the UI or `POST /api/v1/documents`. Files live in `var/documents/`.
2. Pick the snapshots to evaluate—use the live pointer or any specific versions. Selecting multiple snapshots lets you compare outputs.
3. Start a run from the UI or `POST /api/v1/runs`. The engine applies each snapshot and records manifests.
4. Review manifests in the UI or via `GET /api/v1/manifests/{run_id}`. Compare snapshots before promoting new logic.

### Improve extraction logic

1. Create a draft snapshot for the relevant document type.
2. Edit column catalogues, detection logic, schema rules, and profile overrides in the UI.
3. Test drafts against real uploads and review manifest diffs versus the live snapshot.
4. Publish when ready. Publishing advances the live pointer; older snapshots stay immutable for audit and rollback.

### Compare versions in the UI

1. Select documents and the snapshots you want to evaluate (live or historical).
2. Run the comparison. Each snapshot produces its own manifest.
3. Inspect diffs to confirm behaviour changes before promoting logic.

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

Everything in the UI is backed by API routes so automation can follow the same paths.

---

## Authentication and access

- **Username/password** – Default sign-in method. Credentials live in SQLite and are managed in the admin UI.
- **SSO (optional)** – Support a single SAML or OIDC provider if required.
- **Roles** – `viewer`, `editor`, and `admin` determine who can edit logic, publish snapshots, manage users, or issue keys.
- **API keys** – Admins can create API keys tied to a user; keys inherit the user’s role permissions.

Treat the Docker host, SQLite database, and documents directory as sensitive assets.

---

## Storage and backups

- **SQLite (`var/ade.sqlite`)** stores snapshots, manifests, live pointers, users, sessions, and API keys. Snapshot and manifest payloads are JSON blobs to keep migrations light.
- **File storage (`var/documents/`)** holds uploaded documents, fixtures, and exported manifests. Mount it as a Docker volume in production.

Backups require copying the SQLite file and the documents directory together.

---

## Development and deployment

- **Local development** – Run the backend with `uvicorn backend.app.main:app --reload` and the frontend with `npm run dev`. Both use the same SQLite database and documents folder.
- **Single-container deployment** – `docker compose up` builds the combined image and mounts `./var` for persistence.
- **Configuration** – Environment variables cover database paths, document storage, and authentication providers. Defaults point to SQLite and local file storage.
- **Monitoring** – Application logs stream to stdout. Watch `var/` disk usage and the volume of stored manifests.

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

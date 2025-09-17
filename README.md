# ADE — Automatic Data Extractor

ADE turns semi-structured spreadsheets and PDFs into deterministic tables that teams can audit and trust. Because ADE is an internal tool, we optimise for clarity and repeatability instead of extreme scale. A single SQLite database and a folder of uploaded files are enough for everything we do.

---

## Product snapshot

- **Purpose** – Author extraction rules once, rerun them deterministically, and keep a full audit trail of every change.
- **Shape** – One Docker container with a FastAPI backend, Python processing engine, and Vite + TypeScript frontend.
- **Data** – SQLite at `var/ade.sqlite` stores all state; uploaded files live under `var/documents/`.
- **Audience** – Operations, compliance, and engineering teams who want transparent data ingestion.

---

## Guiding principles

1. **Deterministic by default** – Every manifest ties back to an immutable snapshot of extraction logic.
2. **Simple to operate** – If you can copy a SQLite file and a folder of documents, you can back up ADE.
3. **APIs for everything** – The UI and automation hit the same FastAPI routes so scripts never need hidden workflows.
4. **Pure processing logic** – Extraction code runs without side effects, randomness, or network calls to keep results reproducible.

---

## Architecture at a glance

```
+------------------- Docker container -------------------+
| Vite + React UI  <->  FastAPI backend  <->  Processor  |
|                         |                               |
|                         +--> SQLite (var/ade.sqlite)    |
|                         +--> Documents (var/documents/) |
+--------------------------------------------------------+
```

- **Frontend** – Configure document types, edit logic, upload files, compare manifests, and inspect audit notes.
- **FastAPI backend** – Stateless routes for authentication, CRUD, run orchestration, and manifest retrieval.
- **Processing engine** – Pure Python functions that detect headers, map columns, transform values, and validate results.
- **Persistence** – SQLite tables plus the documents directory cover users, snapshots, manifests, audit trails, and uploads. Switch to another database only if the single-file model becomes a bottleneck.

Snapshots drive every run. They bundle detection logic, schema expectations, and optional profile overrides. Runs can evaluate several snapshots side by side so reviewers can compare manifests before promoting new logic.

---

## Domain quick reference

| Concept | Summary |
| --- | --- |
| **Document type** | Family of documents that share extraction rules (e.g., payroll remittances). |
| **Snapshot** | Immutable bundle of logic for a document type. Drafts are editable; published snapshots are read-only. |
| **Profile** | Optional overrides (customer, locale, etc.) that live inside the snapshot payload. |
| **Run** | Execution of one or more snapshots against uploaded documents. |
| **Manifest** | Structured result of a run: detected tables, column mappings, audit notes, and statistics. |

Refer to `ADE_GLOSSARY.md` for precise field names across the API and database.

---

## Everyday workflows

### Upload and process documents

1. Upload files via the UI or `POST /api/v1/documents` (files persist in `var/documents/`).
2. Pick the snapshots to evaluate—use the live pointer or choose specific versions for comparison.
3. Start a run from the UI or `POST /api/v1/runs`. The processor applies each snapshot and stores manifests.
4. Review manifests in the UI or `GET /api/v1/manifests/{run_id}` before promoting new logic.

### Improve extraction logic

1. Create a draft snapshot for the relevant document type.
2. Adjust column catalogues, detection logic, schema rules, and profile overrides.
3. Test drafts against real uploads and inspect manifest diffs versus the live snapshot.
4. Publish when satisfied. Publishing advances the live pointer; previous versions stay immutable for audit and rollback.

### Compare versions in the UI

1. Select documents and the snapshots (live or historical) to evaluate.
2. Run the comparison—each snapshot produces its own manifest.
3. Inspect diffs to confirm behaviour changes before promoting logic.

---

## API quick reference

OpenAPI documentation lives at `/docs`.

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
- **SSO (optional)** – Add one SAML or OIDC provider if required.
- **Roles** – `viewer`, `editor`, and `admin` control who can edit logic, publish snapshots, manage users, or issue keys.
- **API keys** – Admins can create keys tied to users; keys inherit the user’s role permissions.

Treat the Docker host, SQLite database, and documents directory as sensitive assets.

---

## Storage and backups

- **SQLite (`var/ade.sqlite`)** stores snapshots, manifests, live pointers, users, sessions, and API keys. Snapshot and manifest payloads remain JSON blobs to avoid premature schema work.
- **File storage (`var/documents/`)** holds uploads, fixtures, and exported manifests. Mount it as a Docker volume in production.

Backups require copying both the SQLite file and the documents directory.

---

## Development and deployment

- **Local development** – Run the backend with `uvicorn backend.app.main:app --reload` and the frontend with `npm run dev`. Both share the SQLite database and documents folder.
- **Single-container deployment** – `docker compose up` builds the combined image and mounts `./var` for persistence.
- **Configuration** – Environment variables cover database paths, document storage, and authentication providers. Defaults point to SQLite and the local file system.
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

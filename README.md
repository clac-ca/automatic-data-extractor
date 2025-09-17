# ADE — Automatic Data Extractor

ADE is an internal tool that converts semi-structured spreadsheets and PDFs into deterministic tables. The entire platform fits in a single Docker container backed by SQLite and a documents folder, so small teams can run it without extra services.

---

## What ADE solves
- **One repeatable playbook** – Capture extraction rules once and replay them whenever new documents arrive.
- **Auditable history** – Snapshots, manifests, and logs explain how data landed in downstream systems.
- **Operate by copying files** – Back up `var/ade.sqlite` and `var/documents/` together to preserve a deployment.

---

## Design defaults
1. **Deterministic processing** – Every manifest ties back to an immutable snapshot with recorded logic digests.
2. **Plain stack** – FastAPI, SQLite, and TypeScript are enough. Add tools only when a real problem appears.
3. **API-first** – The UI calls the same endpoints that automation scripts use.
4. **Pure logic** – Extraction, transformation, and validation code avoid side effects so reruns stay repeatable.

---

## System at a glance
```
+-------------------- Docker container --------------------+
|  React UI  ↔  FastAPI backend  ↔  Processor helpers       |
|                          |                                 |
|                          ├─ SQLite  (var/ade.sqlite)       |
|                          └─ Documents (var/documents/)     |
+-----------------------------------------------------------+
```
- **Frontend** – Configure document types, edit logic, upload files, review manifests, and compare versions.
- **Backend** – FastAPI routes for auth, CRUD, run orchestration, and manifest retrieval.
- **Processor** – Pure Python helpers that detect tables, map columns, transform values, and collect audit notes.
- **Storage** – SQLite tables and the documents directory cover all persistence. Move away only if volume demands it.

Snapshots power every run: they bundle detection logic, schema expectations, and optional profile overrides. Runs can execute several snapshots side by side so reviewers can compare manifests before promoting new logic.

---

## Domain primer
Key terms such as **document type**, **snapshot**, **run**, and **manifest** appear across the API, database, and UI. See `ADE_GLOSSARY.md` for the naming source of truth.

---

## Everyday flows
### Process new documents
1. Upload files via the UI or `POST /api/v1/documents`; uploads persist in `var/documents/`.
2. Choose snapshots to evaluate (live pointer or historical versions).
3. Trigger a run from the UI or `POST /api/v1/runs`; the processor applies each snapshot and stores manifests in SQLite.
4. Review manifests in the UI or `GET /api/v1/manifests/{run_id}` before promoting new logic.

### Improve extraction logic
1. Create or copy a draft snapshot for the relevant document type.
2. Update column catalogues, detection rules, schema requirements, and profile overrides.
3. Test drafts against real uploads and inspect manifest diffs versus the live snapshot.
4. Publish when satisfied. Publishing advances the live pointer; old snapshots remain immutable.

### Compare versions in the UI
1. Select documents and the snapshots to evaluate.
2. Trigger a comparison run—each snapshot produces its own manifest.
3. Inspect diffs and audit notes to confirm behaviour before promoting logic.

---

## Tech stack & layout
- **Backend** – Python 3.11, FastAPI, SQLAlchemy, and Pydantic v2 under `backend/app/`.
- **Processor** – Pure Python helpers in `backend/processor/`.
- **Frontend** – Vite + React + TypeScript under `frontend/` with strict typing.
- **Infra** – Docker assets under `infra/`.

Planned repository layout:
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

## Operations notes
- **Storage** – SQLite (`var/ade.sqlite`) stores snapshots, manifests, users, sessions, API keys, and audit metadata. Payloads stay as JSON until a real schema need emerges.
- **Documents** – `var/documents/` holds uploads, fixtures, and exported manifests. Mount it as a Docker volume when deploying.
- **Configuration** – Environment variables override defaults; `.env` files hold secrets and stay gitignored.
- **Monitoring** – Logs stream to stdout. Watch the size of `var/` and run durations.

Backing up ADE means copying both the SQLite file and the documents directory.

---

## Development and deployment
- **Local** – Run the backend with `uvicorn backend.app.main:app --reload` and the frontend with `npm run dev`; both share the same SQLite database and documents folder.
- **Single-container deploy** – `docker compose up` builds the combined image and mounts `./var` for persistence.
- **Quality** – Use pytest, ruff, mypy, and the frontend test/typecheck commands when relevant.

---

## Near-term roadmap
- Guided rule authoring that surfaces example matches and misses.
- Snapshot comparison reports summarising behaviour changes across batches.
- Bulk uploads and optional background processing once single-run workflows become limiting.

---

## License
TBD.

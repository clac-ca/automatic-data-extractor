# ADE — Automatic Data Extractor

ADE is a single-container internal tool that turns repeating spreadsheets and PDFs into deterministic tables. Everything ships
together: a FastAPI backend, a pure-Python processor, a React UI, and a SQLite database with documents on disk so teams can run
it without extra services.

---

## Guiding principles
- **Deterministic runs** – Every manifest ties back to an immutable snapshot with recorded logic digests.
- **Boring technology** – FastAPI, SQLite, and TypeScript are enough. Reach for new tools only when a real limitation appears.
- **One API surface** – The UI and automation scripts talk to the same HTTP endpoints.
- **Pure extraction logic** – Processing code stays side-effect free so reruns always match.

---

## Architecture overview
```
+------------------------ Docker container -----------------------+
|  React UI  ↔  FastAPI backend  ↔  Processor helpers             |
|                              |                                   |
|                              ├─ SQLite database  (var/ade.sqlite)|
|                              └─ Document storage (var/documents/)|
+-----------------------------------------------------------------+
```
- **Frontend** – Configure document types, edit logic, upload files, review manifests, and compare versions.
- **Backend** – FastAPI routes for auth, CRUD, run orchestration, and manifest retrieval.
- **Processor** – Pure Python helpers that detect tables, map columns, transform values, and collect audit notes.
- **Storage** – SQLite and the documents directory handle all persistence. Move away only if volume demands it.

Snapshots power every run: they bundle detection logic, schema expectations, and optional profile overrides. Runs can evaluate
multiple snapshots side by side so reviewers can compare manifests before promoting new logic.

---

## Core workflows
### Process new documents
1. Upload files via the UI or `POST /api/v1/documents`; uploads persist in `var/documents/`.
2. Choose the snapshots to evaluate (live pointer or historical versions).
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

## Data & terminology
The glossary in `ADE_GLOSSARY.md` defines the terms used across the API, database, and UI. Treat it as the naming authority for
code, payloads, and documentation.

---

## Tech stack & repository layout
- **Backend** – Python 3.11, FastAPI, SQLAlchemy, and Pydantic v2 under `backend/app/`.
- **Processor** – Pure Python helpers in `backend/processor/`.
- **Frontend** – Vite + React + TypeScript under `frontend/` with strict typing enabled.
- **Infra** – Docker assets under `infra/`.

Planned layout:
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

## Operations & data handling
- SQLite (`var/ade.sqlite`) stores snapshots, manifests, users, sessions, API keys, and audit metadata. Payloads stay JSON until
  a strict schema is required.
- `var/documents/` holds uploads, fixtures, and exported manifests. Mount it as a Docker volume when deploying.
- Environment variables override defaults; `.env` files hold secrets and stay gitignored.
- Logs stream to stdout. Keep an eye on `var/` size and run durations.

Backing up ADE means copying both the SQLite file and the documents directory.

---

## Development
- Run the backend with `uvicorn backend.app.main:app --reload`.
- Run the frontend with `npm run dev`. Both reuse the same SQLite database and documents folder.
- Provide a combined workflow with `docker compose up` that mounts `./var` for persistence.
- Use pytest, ruff, mypy, and the frontend lint/typecheck commands when you change related areas.

---

## Near-term roadmap
- Guided rule authoring that surfaces example matches and misses.
- Snapshot comparison reports summarising behaviour changes across batches.
- Bulk uploads and optional background processing once single-run workflows become limiting.

---

## License
TBD.

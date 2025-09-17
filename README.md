# ADE — Automatic Data Extractor

ADE is an internal tool shipped as a single Docker container. The bundle includes a FastAPI backend, a pure-Python extraction
engine, a React UI, and a SQLite database with documents on disk. Teams can run it on a laptop or a small server without any
extra services.

---

## System snapshot
```
+----------------------------- Docker container -----------------------------+
|  React UI  ↔  FastAPI backend  ↔  Pure-Python processor helpers             |
|                                     |                                       |
|                                     ├─ SQLite database  (var/ade.sqlite)    |
|                                     └─ Document storage (var/documents/)    |
+-----------------------------------------------------------------------------
```
- **Frontend** – Configure document types, edit extraction logic, upload files, compare manifests, and publish new snapshots.
- **Backend** – FastAPI routes for auth, CRUD, run orchestration, and manifest retrieval.
- **Processor** – Pure functions that locate tables, map columns, transform values, and emit audit notes.
- **Storage** – SQLite and the on-disk documents directory keep persistence simple. Switch only when scale truly demands it.

---

## Design tenets
- **Deterministic by default** – Every manifest links back to an immutable snapshot with digests of the logic used.
- **Choose boring tech** – FastAPI, SQLite, and TypeScript are enough. Reach for new dependencies only when the simple stack
  blocks us.
- **One API surface** – UI, automation scripts, and background jobs all call the same HTTP endpoints.
- **Pure extraction logic** – Processing code is side-effect free so reruns always match prior outputs.
- **Operational clarity** – Favour readable code, explicit logging, and shallow dependency trees over raw throughput.

---

## Building blocks
### Frontend
Lives under `frontend/` (Vite + React + TypeScript). It lets reviewers upload documents, inspect manifests, and manage
snapshots. Strict typing and lightweight components keep the UI predictable.

### Backend
Resides in `backend/app/` (Python 3.11, FastAPI, SQLAlchemy, Pydantic v2). It owns routing, authentication, orchestration, and
persistence helpers. Domain logic that manipulates data stays out of request handlers and in focused service modules.

### Processor
Pure Python helpers live in `backend/processor/`. They detect tables, decide column mappings, run validation rules, and produce
audit notes. Because they are deterministic functions, reruns against the same snapshot + document yield identical manifests.

### Storage
All persistence uses SQLite (`var/ade.sqlite`) and an on-disk documents folder (`var/documents/`). These paths are gitignored
and mounted as Docker volumes in deployment.

---

## How the system flows
1. Upload documents through the UI or `POST /api/v1/documents`. Files land in `var/documents/`.
2. Select one or more snapshots (live or historical) to evaluate.
3. Trigger a run via the UI or `POST /api/v1/runs`. The processor executes each snapshot and writes manifests to SQLite.
4. Review manifests in the UI or by calling `GET /api/v1/manifests/{run_id}`. Promote new snapshots when the results look right.
5. Published snapshots advance the live pointer for that document type; older snapshots remain immutable.

---

## Data naming authority
The glossary in `ADE_GLOSSARY.md` defines every API field, database column, and UI label. Treat it as the source of truth when
naming payloads or schema elements.

---

## Repository layout (planned)
```
.
├─ README.md
├─ ADE_GLOSSARY.md
├─ AGENTS.md
├─ backend/
│  ├─ app/            # FastAPI entrypoint, routes, schemas, services
│  ├─ processor/      # Table detection, column mapping, validation logic
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

## Operations
- SQLite stores snapshots, manifests, users, sessions, API keys, and audit metadata. Payloads stay JSON until a strict schema is
  required.
- Back up ADE by copying both the SQLite file and the documents directory.
- Environment variables override defaults; `.env` files hold secrets and stay gitignored.
- Logs stream to stdout. Keep an eye on `var/` size and long-running jobs.

---

## Development routines
- Backend: `uvicorn backend.app.main:app --reload`.
- Frontend: `npm run dev`. Both reuse the same SQLite database and documents directory.
- Docker: `docker compose up` builds the container and mounts `./var` for persistence.
- Quality checks: pytest, ruff, mypy, plus `npm test`, `npm run lint`, and `npm run typecheck` for UI changes.

---

## Near-term roadmap
- Guided rule authoring with inline examples of matches and misses.
- Snapshot comparison reports summarising behaviour changes across document batches.
- Bulk uploads and optional background processing once single-run workflows become limiting.

---

## License
TBD.

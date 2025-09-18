# ADE — Automatic Data Extractor

ADE is an internal tool shipped as a single Docker container. The bundle includes a FastAPI backend, a pure-Python extraction
engine, a React UI, and a SQLite database with documents on disk. Teams can run it on a laptop or a small server without any
extra services.

---

## System overview
```
+----------------------------- Docker container -----------------------------+
|  React UI  ↔  FastAPI backend  ↔  Pure-Python processor helpers             |
|                                     |                                       |
|                                     ├─ SQLite database  (var/ade.sqlite)    |
|                                     └─ Document storage (var/documents/)    |
+-----------------------------------------------------------------------------
```
- **Frontend** – Manage document-type configurations, edit extraction logic, upload files, launch jobs, review job results, and activate new configuration revisions.
- **Backend** – FastAPI routes for auth, CRUD, document ingestion, job orchestration, and job result retrieval.
- **Processor** – Pure functions that locate tables, map columns, transform values, and emit audit notes.
- **Storage** – SQLite and the on-disk documents directory keep persistence simple. Switch only when scale truly demands it.

---

## Design tenets
- **Deterministic by default** – Every job links back to the configuration revision that produced it, complete with digests of the logic used.
- **Choose boring tech** – FastAPI, SQLite, and TypeScript are enough. Reach for new dependencies only when the simple stack
  blocks us.
- **One API surface** – UI, automation scripts, and background jobs all call the same HTTP endpoints.
- **Pure extraction logic** – Processing code is side-effect free so reruns always match prior outputs.
- **Operational clarity** – Favour readable code, explicit logging, and shallow dependency trees over raw throughput.

---

## Building blocks
### Frontend
Lives under `frontend/` (Vite + React + TypeScript). It lets reviewers upload documents, monitor jobs, inspect job outputs, and manage configuration revisions. Strict typing and lightweight components keep the UI predictable.

### Backend
Resides in `backend/app/` (Python 3.11, FastAPI, SQLAlchemy, Pydantic v2). It owns routing, authentication, orchestration, and
persistence helpers. Domain logic that manipulates data stays out of request handlers and in focused service modules. The
initial foundation created here wires together:

- `config.py` – centralised settings (`ADE_` environment variables, SQLite + documents defaults).
- `db.py` – SQLAlchemy engine/session helpers shared across routes and services.
- `models.py` – the first domain models (`ConfigurationRevision`, `Job`, and `Document`) with ULID keys, JSON payload storage, and hashed document URIs.
- `routes/health.py` – health check hitting the database and returning `{ "status": "ok" }`.
- `routes/documents.py` – multipart uploads, metadata listings, and download streaming for stored documents.
- `main.py` – FastAPI application setup, startup lifecycle, and router registration.
- `services/documents.py` – hashed-path storage, deduplication on SHA-256, and filesystem lookups for uploads.
- `tests/` – pytest-based checks that assert the service boots and SQLite file creation works.

### Processor
Pure Python helpers live in `backend/processor/`. They detect tables, decide column mappings, run validation rules, and produce audit notes. Because they are deterministic functions, reruns against the same configuration revision and document yield identical job results.

### Storage
All persistence uses SQLite (`var/ade.sqlite`) and an on-disk documents folder (`var/documents/`). These paths are gitignored
and mounted as Docker volumes in deployment.

---

## How the system flows
1. Upload documents through the UI or `POST /documents`. The backend stores the file under a hashed path in `var/documents/` and returns canonical metadata (including the `stored_uri` jobs reference later).
2. Create or edit configuration revisions, then activate the revision that should run by default for the document type.
3. Launch a job via the UI or `POST /jobs`. The processor applies the active configuration revision and records job inputs, outputs, metrics, and logs.
4. Poll `GET /jobs/{job_id}` (or list with `GET /jobs`) to review progress, download output artefacts, and inspect metrics.
5. Promote new configuration revisions when results look right; only one active revision exists per document type at a time.

---

## Job record format
Jobs returned by the API and displayed in the UI always use the same JSON structure:

```jsonc
{
  "job_id": "job_2025_09_17_0001",
  "document_type": "Remittance PDF",
  "configuration_revision": 3,

  "status": "completed",
  "created_at": "2025-09-17T18:42:00Z",
  "updated_at": "2025-09-17T18:45:11Z",
  "created_by": "jkropp",

  "input": {
    "uri": "var/documents/remit_2025-09.pdf",
    "hash": "sha256:a93c...ff12",
    "expires_at": "2025-10-01T00:00:00Z"
  },

  "outputs": {
    "json": {
      "uri": "var/outputs/remit_2025-09.json",
      "expires_at": "2026-01-01T00:00:00Z"
    },
    "excel": {
      "uri": "var/outputs/remit_2025-09.xlsx",
      "expires_at": "2026-01-01T00:00:00Z"
    }
  },

  "metrics": {
    "rows_extracted": 125,
    "processing_time_ms": 4180,
    "errors": 0
  },

  "logs": [
    { "ts": "2025-09-17T18:42:00Z", "level": "info", "message": "Job started" },
    { "ts": "2025-09-17T18:42:01Z", "level": "info", "message": "Detected table 'MemberContributions'" },
    { "ts": "2025-09-17T18:44:59Z", "level": "info", "message": "125 rows processed" },
    { "ts": "2025-09-17T18:45:11Z", "level": "info", "message": "Job completed successfully" }
  ]
}
```

---

## Document ingestion workflow

1. `POST /documents` accepts a multipart upload (`file` field). The API streams the payload into `var/documents/<sha256-prefix>/...` and returns metadata including `document_id`, byte size, digest, and the canonical `stored_uri`.
2. Uploading identical bytes returns the existing record and reuses the stored file. If the on-disk file has gone missing, the upload restores it before responding.
3. `GET /documents` lists records newest first, `GET /documents/{document_id}` returns metadata for a single file, and `GET /documents/{document_id}/download` streams the stored bytes (with `Content-Disposition` set to the original filename).
4. TODO: enforce an explicit request size limit so large uploads receive a clear 413 response. For now FastAPI's defaults stream uploads but do not cap request size.

---

## Data naming authority
The glossary in `ADE_GLOSSARY.md` defines every API field, database column, and UI label. Treat it as the source of truth when
naming payloads or configuration elements.

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
├─ runs/              # Example job outputs
└─ var/
   ├─ documents/      # Uploaded files (gitignored)
   └─ ade.sqlite      # Local development database (gitignored)
```

---

## Operations
- SQLite stores configuration revisions, jobs, users, sessions, API keys, and audit metadata. Payloads stay JSON until a strict configuration is required.
- Back up ADE by copying both the SQLite file and the documents directory.
- Environment variables override defaults; `.env` files hold secrets and stay gitignored.
- Logs stream to stdout. Keep an eye on `var/` size and long-running jobs.

---

Here’s a polished section you can drop into your **README.md** under development routines. It’s focused on **Windows (PowerShell)** and written in the same professional style as the rest of your docs:

---

Looks solid. Here’s a tightened, dev-friendly version you can drop in. I kept the tone crisp, fixed small typos, and added tiny guardrails (prereqs + quick smoke test + common fixes).

---

## Local testing (no Docker, Windows PowerShell)

Run ADE locally for fast backend/UI iteration. Commands assume **Windows 10/11** with **PowerShell**.

### Prerequisites

* **Python 3.11+**
* **Node.js 20+** (for the frontend)
* **Git**
* (Optional) **Docker** for the containerized flow

### 1) Backend (FastAPI + SQLite)

```powershell
# From the project root
cd C:\Github\automatic-data-extractor

# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project deps (from pyproject.toml), incl. dev extras (pytest)
pip install -e ".[dev]"

# Start the API with auto-reload
python -m uvicorn backend.app.main:app --reload
# → http://127.0.0.1:8000
```

**Smoke check (new tab):**

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health | Select-Object -ExpandProperty Content
```

### 2) Frontend (React + Vite)

```powershell
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173 (expects backend at http://localhost:8000)
```

### 3) Tests & Quality

```powershell
# Backend tests
pytest -q

# Python quality
ruff check
mypy

# Frontend quality
npm test
npm run lint
npm run typecheck
```

### Notes & quick fixes

* **Activate the venv** (`.\.venv\Scripts\Activate.ps1`) before running Python tools.
* If `uvicorn` isn’t found, use `python -m uvicorn …`.
* If PowerShell blocks activation, run:

  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```
* If port **8000** is in use:

  ```powershell
  python -m uvicorn backend.app.main:app --reload --port 8001
  ```

---

## Near-term roadmap
- Guided rule authoring with inline examples of matches and misses.
- Revision comparison reports summarising behaviour changes across document batches.
- Bulk uploads and optional background processing once single-run workflows become limiting.

---

## License
TBD.

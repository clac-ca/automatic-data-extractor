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

- `config.py` – centralised settings (`ADE_` environment variables, SQLite + documents defaults, upload size cap).
- `db.py` – SQLAlchemy engine/session helpers shared across routes and services.
- `models.py` – the first domain models (`ConfigurationRevision`, `Job`, and `Document`) with ULID identifiers, JSON payload storage, and predictable document URIs.
- `routes/health.py` – health check hitting the database and returning `{ "status": "ok" }`.
- `routes/documents.py` – multipart uploads, metadata listings, download streaming, and manual deletion for stored documents.
- `routes/events.py` – paginated event listings plus document, configuration, and job timeline endpoints.
- `main.py` – FastAPI application setup, startup lifecycle, and router registration.
- `services/documents.py` – ULID-based storage for uploads, size-limit enforcement, filesystem lookups, and soft-delete helpers.
- `services/events.py` – shared helper for recording immutable events and querying them with consistent filters.
- `tests/` – pytest-based checks that assert the service boots and SQLite file creation works.

### Processor
Pure Python helpers live in `backend/processor/`. They detect tables, decide column mappings, run validation rules, and produce audit notes. Because they are deterministic functions, reruns against the same configuration revision and document yield identical job results.

### Storage
All persistence uses SQLite (`var/ade.sqlite`) and an on-disk documents folder (`var/documents/`). These paths are gitignored
and mounted as Docker volumes in deployment.

### Identifier strategy
Documents, configurations, and events share the same ULID format for their primary keys and, in the case of documents, their stored filenames. UUIDv4 identifiers are widely standardised and perfectly random, which makes them a safe universal default, but that randomness also scatters writes across a database index and increases fragmentation. ULIDs remain 128-bit identifiers while adding a 48-bit timestamp prefix, so new values stay lexicographically sorted, keep SQLite indexes append-friendly, and preserve chronological ordering even if multiple workers generate IDs. We will stick with ULIDs for ADE’s ingestion-heavy workflows, while reserving UUIDv4s for situations where external interoperability or strict standards compliance outweigh those locality benefits.

### Events
ADE keeps an immutable event log in the `events` table. The helper at `services/events.record_event(...)` accepts a typed payload, canonicalises any JSON context for deterministic storage, and persists a ULID-keyed row. Clients query events through the same service or via `/events`, which supports pagination plus filters for entity, event type, actor metadata, source, request ID, and time bounds. When callers provide both `entity_type` and `entity_id` the global feed resolves that entity once and reuses the same summary block emitted by the timeline endpoints, so document tools can render context (filename, title, status, etc.) without issuing another lookup.

Core event families include:

- `document.deleted` – records soft deletions with byte-size, checksum, delete reason, and the actor/source that initiated the removal.
- `configuration.created`, `configuration.updated`, `configuration.activated` – capture configuration titles, versions, activation state, and which actor changed them.
- `job.created`, `job.status.*`, `job.results.published` – log job creation, state transitions, and when outputs/metrics are published.

The API surfaces these records directly.

#### Document events

A `document.deleted` entry looks like:

```jsonc
{
  "event_id": "01JABCXY45MNE678PQRS012TU3",
  "event_type": "document.deleted",
  "entity_type": "document",
  "entity_id": "01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
  "occurred_at": "2024-08-02T17:25:14.123456+00:00",
  "actor_type": "user",
  "actor_label": "ops@ade.local",
  "source": "api",
  "payload": {
    "deleted_by": "ops@ade.local",
    "delete_reason": "cleanup",
    "byte_size": 542118,
    "stored_uri": "uploads/01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
    "sha256": "sha256:bd5c3d9a...",
    "expires_at": "2025-10-17T18:42:00+00:00"
  }
}
```

`PATCH /documents/{document_id}` merges metadata updates into the stored
record and appends a `document.metadata.updated` event (or a caller supplied
`event_type`). Event payloads capture the changed values, list which metadata
keys were modified, and note any keys that were removed so downstream tools can
reconstruct context without refetching the document.

#### Configuration events

Configuration rows emit immutable entries as drafts are created, metadata changes, and activations occur.

```jsonc
{
  "event_type": "configuration.created",
  "entity_type": "configuration",
  "actor_label": "api",
  "payload": {
    "document_type": "invoice",
    "title": "Invoice v1",
    "version": 3,
    "is_active": false
  }
}
```

```jsonc
{
  "event_type": "configuration.updated",
  "entity_type": "configuration",
  "actor_label": "api",
  "payload": {
    "document_type": "invoice",
    "title": "Invoice v2",
    "version": 3,
    "is_active": true,
    "changed_fields": ["is_active"]
  }
}
```

```jsonc
{
  "event_type": "configuration.activated",
  "entity_type": "configuration",
  "actor_label": "api",
  "source": "api",
  "payload": {
    "document_type": "invoice",
    "title": "Invoice v3",
    "version": 4,
    "is_active": true,
    "activated_at": "2025-01-10T08:01:12+00:00"
  }
}
```

#### Job events

Jobs append events as they are created, progress through statuses, and publish outputs or metrics.

```jsonc
{
  "event_type": "job.created",
  "entity_type": "job",
  "actor_label": "ops@ade.local",
  "payload": {
    "document_type": "remittance",
    "configuration_id": "01JCFG7890ABCDEFFEDCBA3210",
    "configuration_version": 7,
    "status": "pending",
    "created_by": "ops@ade.local",
    "input": {
      "uri": "var/documents/remit_final.pdf",
      "sha256": "sha256:bd5c3d9a..."
    }
  }
}
```

```jsonc
{
  "event_type": "job.status.completed",
  "entity_type": "job",
  "actor_label": "api",
  "payload": {
    "document_type": "remittance",
    "configuration_id": "01JABCXY45MNE678PQRS012TU3",
    "configuration_version": 7,
    "status": "completed",
    "from_status": "running",
    "to_status": "completed"
  }
}
```

```jsonc
{
  "event_type": "job.results.published",
  "entity_type": "job",
  "actor_label": "api",
  "payload": {
    "document_type": "remittance",
    "configuration_id": "01JCFG7890ABCDEFFEDCBA3210",
    "configuration_version": 7,
    "status": "completed",
    "outputs": {
      "json": {
        "uri": "var/outputs/remit_final.json",
        "expires_at": "2026-01-01T00:00:00Z"
      }
    },
    "metrics": {
      "rows_extracted": 125,
      "processing_time_ms": 4180,
      "errors": 0
    }
  }
}
```

Logging is additive—failures to append an event are logged but do not roll back the underlying workflow. Litigation hold remains out of scope; extend payloads if special handling is required.

---

## How the system flows
1. Upload documents through the UI or `POST /documents`. The backend writes the file to `var/documents/uploads/{document_id}` using the document ULID and returns canonical metadata (including the `stored_uri` jobs reference later).
2. Create or edit configurations, then activate the configuration that should run by default for the document type.
3. Launch a job via the UI or `POST /jobs`. The processor applies the active configuration and records job inputs, outputs, metrics, and logs.
4. Poll `GET /jobs/{job_id}` (or list with `GET /jobs`) to review progress, download output artefacts, and inspect metrics.
5. Promote new configurations when results look right; only one active configuration exists per document type at a time.

---

## Job record format
Jobs returned by the API and displayed in the UI always use the same JSON structure:

```jsonc
{
  "job_id": "job_2025_09_17_0001",
  "document_type": "Remittance PDF",
  "configuration_version": 3,

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

1. `POST /documents` accepts a multipart upload (`file` field). The API streams the payload into `var/documents/uploads/{document_id}` and returns metadata including `document_id`, byte size, digest, and the canonical `stored_uri`.
2. Every upload creates a fresh document record with its own storage path, even if the raw bytes match a prior submission.
3. `GET /documents` lists records newest first, `GET /documents/{document_id}` returns metadata for a single file, `GET /documents/{document_id}/download` streams the stored bytes (with `Content-Disposition` set to the original filename), and `DELETE /documents/{document_id}` removes the bytes while recording who initiated the deletion. `GET /documents/{document_id}/events` exposes the immutable history of deletion events for that record and includes an `entity` summary with the filename, type, byte size, checksum, expiration, and deletion markers. Configuration revisions use `GET /configurations/{configuration_id}/events` and jobs use `GET /jobs/{job_id}/events`; all timeline endpoints share pagination and filtering behaviour with the global events feed and embed the headline fields the UI needs. When `/events` is filtered to a specific entity, it inlines the same summary block so consumers see consistent context across feeds.
4. `POST /documents` enforces the configurable `max_upload_bytes` cap (defaults to 25 MiB). Payloads that exceed the limit return HTTP 413 with `{ "detail": {"error": "document_too_large", "max_upload_bytes": <bytes>, "received_bytes": <bytes>}}` so operators know the request failed before any data is persisted.
5. Document retention and deletion workflows are defined in `docs/document_retention_and_deletion.md`. The API records manual deletions, logs them to the shared events feed, runs an automatic purge sweep on startup (and hourly by default), and still exposes a maintenance CLI (`python -m backend.app.maintenance.purge`) for manual runs.

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
- SQLite stores configuration revisions, jobs, users, sessions, API keys, and event metadata. Payloads stay JSON until a strict configuration is required.
- Back up ADE by copying both the SQLite file and the documents directory.
- Environment variables override defaults; `.env` files hold secrets and stay gitignored. Set `ADE_MAX_UPLOAD_BYTES` (bytes) to raise or lower the upload cap. Keep the value conservative so operators can predict disk usage.
- Document retention defaults to 30 days (`ADE_DEFAULT_DOCUMENT_RETENTION_DAYS`). Callers can override the expiry per upload via the `expires_at` form field on `POST /documents`.
- The backend purges expired documents automatically inside the API process. Set `ADE_PURGE_SCHEDULE_ENABLED=false` to disable it, `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` (default `3600`) to control the sweep cadence, and `ADE_PURGE_SCHEDULE_RUN_ON_STARTUP=false` to skip the initial run when the service boots.
- Logs stream to stdout. Keep an eye on `var/` size and long-running jobs.

### Purging expired documents

- The API checks for expired documents on startup and then every `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS` seconds (default: 3600). Each run logs a structured summary with counts for processed files, missing paths, and reclaimed bytes. The scheduler also persists the latest results in SQLite (`maintenance_status` table) and surfaces them under the `purge` key on `GET /health` so operators can inspect the most recent sweep without scraping logs.
- Keep the automatic scheduler enabled for day-to-day operations. When troubleshooting or before rolling configuration changes, run `python -m backend.app.maintenance.purge` manually to see the same summary interactively.
- Shorten the cadence locally by exporting `ADE_PURGE_SCHEDULE_INTERVAL_SECONDS=5` before starting the API. Upload a throwaway document and call `/health` to watch the `purge` section update with `status`, counts, timestamps, and the configured interval.
- `--dry-run` reports the documents that would be removed without touching the filesystem or database so you can alert on upcoming deletions before enabling destructive runs.
- `--limit` caps how many documents are processed in a single invocation so operators can sweep large queues incrementally.
- The command logs a structured summary (processed count, missing files, reclaimed bytes) and prints a human-readable report so cron jobs and humans see the same outcome.

## Local development (Windows PowerShell, no Docker)

Run ADE locally for fast backend/UI iteration without Docker. Commands assume **Windows 10/11** with **PowerShell**.

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

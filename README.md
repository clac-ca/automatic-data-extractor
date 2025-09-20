# ADE — Automatic Data Extractor

ADE is an internal tool shipped as a single Docker container. The bundle includes a FastAPI backend, a pure-Python extraction
engine, a React UI, and a SQLite database with documents on disk. Teams can run it on a laptop or a small server without any
extra services.

---

## Documentation

Start with the [documentation hub](docs/README.md) for persona-specific guides, runbooks, and references.

## System overview

The architecture diagram, component responsibilities, and job lifecycle are documented in [docs/foundation/system-overview.md](docs/foundation/system-overview.md).

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
- `models.py` – domain models covering configurations, jobs, documents, users, sessions, and audit events. All tables share ULID identifiers and deterministic timestamps.
- `routes/health.py` – health check hitting the database and returning `{ "status": "ok" }`.
- `routes/documents.py` – multipart uploads, metadata listings, download streaming, and manual deletion for stored documents.
- `routes/events.py` – paginated event listings plus document, configuration, and job timeline endpoints.
- `routes/auth.py` – login/logout/session endpoints backed by HTTP Basic, cookie sessions, and optional SSO callbacks.
- `main.py` – FastAPI application setup, startup lifecycle, and router registration.
- `auth/` – password hashing helpers, session persistence, request dependencies, OIDC utilities, and a CLI for provisioning users.
- `services/documents.py` – ULID-based storage for uploads, size-limit enforcement, filesystem lookups, and soft-delete helpers.
- `services/events.py` – shared helper for recording immutable events and querying them with consistent filters.
- `tests/` – pytest-based checks that assert the service boots and SQLite file creation works.

### Processor
Pure Python helpers live in `backend/processor/`. They detect tables, decide column mappings, run validation rules, and produce audit notes. Because they are deterministic functions, reruns against the same configuration revision and document yield identical job results.

### Storage
All persistence uses SQLite (`var/ade.sqlite`) and an on-disk documents folder (`var/documents/`). These paths are gitignored
and mounted as Docker volumes in deployment.

### Authentication
ADE exposes a small set of authentication modes controlled by the `ADE_AUTH_MODES` environment variable:

- `basic` (default) – enable HTTP Basic credentials plus the cookie-backed sessions the UI expects.
- `sso` – layer OIDC sign-in alongside the default sessions.
- `none` – disable authentication entirely so every request runs with administrator privileges (handy for demos).

Session cookies are always issued when authentication is active, so there is no separate `session` toggle. Key environment
variables include:

- `ADE_AUTH_MODES` – comma separated list drawn from `none`, `basic`, and `sso` (default: `basic`).

- `ADE_SESSION_COOKIE_NAME`, `ADE_SESSION_TTL_MINUTES`, `ADE_SESSION_COOKIE_SECURE`, `ADE_SESSION_COOKIE_DOMAIN`,
  `ADE_SESSION_COOKIE_SAME_SITE` – control browser session behaviour.
- `ADE_SSO_CLIENT_ID`, `ADE_SSO_CLIENT_SECRET`, `ADE_SSO_ISSUER`, `ADE_SSO_REDIRECT_URL`, `ADE_SSO_AUDIENCE`,
  `ADE_SSO_CACHE_TTL_SECONDS` – configure
  standards-compliant code exchanges when `sso` mode is active.

API key authentication is under development and will sit alongside these modes. Integrations should prepare to send an `ADE-API-Key` header sourced from a per-service secret (for example, `ADE_API_KEY`) while still honouring the session cookie the UI relies on.

User accounts live in the `users` table. A lightweight CLI (`python -m backend.app.auth.manage`) manages accounts with
`create-user`, `reset-password`, `deactivate`, `promote`, and `list-users` commands. CLI operations emit events so audit logs
capture administrative changes even when the API is offline.

SSO environments expect RS256-signed ID tokens. ADE caches the provider discovery document and JWKS payloads for the configured
TTL (`ADE_SSO_CACHE_TTL_SECONDS`) while still rejecting expired tokens or IDs signed by unknown keys.

### Identifier strategy
Documents, configurations, and events share the same ULID format for their primary keys and, in the case of documents, their stored filenames. UUIDv4 identifiers are widely standardised and perfectly random, which makes them a safe universal default, but that randomness also scatters writes across a database index and increases fragmentation. ULIDs remain 128-bit identifiers while adding a 48-bit timestamp prefix, so new values stay lexicographically sorted, keep SQLite indexes append-friendly, and preserve chronological ordering even if multiple workers generate IDs. We will stick with ULIDs for ADE’s ingestion-heavy workflows, while reserving UUIDv4s for situations where external interoperability or strict standards compliance outweigh those locality benefits.

### Events
ADE keeps an immutable event log in the `events` table. The helper at `services/events.record_event(...)` accepts a typed payload, canonicalises any JSON context for deterministic storage, and persists a ULID-keyed row. Clients query events through the same service or via `/events`, which supports pagination plus filters for entity, event type, actor metadata, source, request ID, and time bounds. When callers provide both `entity_type` and `entity_id` the global feed resolves that entity once and reuses the same summary block emitted by the timeline endpoints, so document tools can render context (filename, title, status, etc.) without issuing another lookup.

Core event families include:

- `document.deleted` – records soft deletions with byte-size, checksum, delete reason, and the actor/source that initiated the removal.
- `configuration.created`, `configuration.updated`, `configuration.activated` – capture configuration titles, versions, activation state, and which actor changed them.
- `job.created`, `job.status.*`, `job.metrics.updated` – log job creation, state transitions, and when metrics snapshots change.

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
  "event_type": "job.metrics.updated",
  "entity_type": "job",
  "actor_label": "api",
  "payload": {
    "document_type": "remittance",
    "configuration_id": "01JCFG7890ABCDEFFEDCBA3210",
    "configuration_version": 7,
    "status": "completed",
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
3. Launch a job via the UI or `POST /jobs`, supplying the `input_document_id` for the source file. The processor applies the active configuration and records metrics and logs alongside the job. Derived outputs are uploaded later by calling `POST /documents` with `produced_by_job_id` set to the job identifier.
4. Poll `GET /jobs/{job_id}` (or list with `GET /jobs`, optionally filtering by `input_document_id`) to review progress, download output artefacts, and inspect metrics. Use `GET /documents/{document_id}/jobs` to show the processing history for a specific file without scanning the full job list.
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

  "input_document": {
    "document_id": "01J8Z0Z4YV6N9Q8XCN5P7Q2RSD",
    "original_filename": "remittance.pdf",
    "content_type": "application/pdf",
    "byte_size": 542118,
    "created_at": "2025-09-17T18:42:00Z",
    "is_deleted": false,
    "download_url": "/documents/01J8Z0Z4YV6N9Q8XCN5P7Q2RSD/download"
  },

  "output_documents": [
    {
      "document_id": "01J8Z0Z4YV6N9Q8XCN5P7Q2RSE",
      "original_filename": "remit.json",
      "content_type": "application/json",
      "byte_size": 12345,
      "created_at": "2025-09-17T18:45:10Z",
      "is_deleted": false,
      "download_url": "/documents/01J8Z0Z4YV6N9Q8XCN5P7Q2RSE/download"
    },
    {
      "document_id": "01J8Z0Z4YV6N9Q8XCN5P7Q2RSF",
      "original_filename": "remit.xlsx",
      "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "byte_size": 98765,
      "created_at": "2025-09-17T18:45:11Z",
      "is_deleted": false,
      "download_url": "/documents/01J8Z0Z4YV6N9Q8XCN5P7Q2RSF/download"
    }
  ],

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


`input_document` and `output_documents` keep the UI aware of every related file without parsing storage URIs. The persisted pointers are `input_document_id` on the job and `produced_by_job_id` on each document.

---

## Document ingestion workflow

1. `POST /documents` accepts a multipart upload (`file` field). The API streams the payload into `var/documents/uploads/{document_id}` and returns metadata including `document_id`, byte size, digest, and the canonical `stored_uri`.
2. Every upload creates a fresh document record with its own storage path, even if the raw bytes match a prior submission.
3. `GET /documents` lists records newest first, `GET /documents/{document_id}` returns metadata for a single file, `GET /documents/{document_id}/download` streams the stored bytes (with `Content-Disposition` set to the original filename), and `DELETE /documents/{document_id}` removes the bytes while recording who initiated the deletion. `GET /documents/{document_id}/events` exposes the immutable history of deletion events for that record and includes an `entity` summary with the filename, type, byte size, checksum, expiration, and deletion markers. `GET /documents/{document_id}/jobs` lists the jobs linked to that document (respecting the same `limit`/`offset` bounds as the other timelines), and `/jobs` accepts an `input_document_id` query parameter when the global list needs to be filtered. Configuration revisions use `GET /configurations/{configuration_id}/events` and jobs use `GET /jobs/{job_id}/events`; all timeline endpoints share pagination and filtering behaviour with the global events feed and embed the headline fields the UI needs. When `/events` is filtered to a specific entity, it inlines the same summary block so consumers see consistent context across feeds.
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

## Local development

Use the platform guides for step-by-step setup and configuration management.

- [Local quickstart (Windows PowerShell)](docs/platform/quickstart-local.md) walks through creating a virtual environment, running the backend, and starting the Vite dev server.
- [Environment and secret management](docs/platform/environment-management.md) explains how `.env` files, overrides, and restarts work together.

---

## Near-term roadmap
- Guided rule authoring with inline examples of matches and misses.
- Revision comparison reports summarising behaviour changes across document batches.
- Bulk uploads and optional background processing once single-run workflows become limiting.

---

## License
TBD.

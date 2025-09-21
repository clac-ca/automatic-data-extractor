---
Audience: Platform administrators, IT architects
Goal: Provide a high-level view of ADE's architecture, component responsibilities, and job lifecycle for evaluation and onboarding.
Prerequisites: Familiarity with containerised deployments and the terminology defined in the [ADE glossary](../../ADE_GLOSSARY.md).
When to use: Share with reviewers who need to understand trust boundaries, component roles, and how documents flow through ADE.
Validation: Ensure the ASCII diagram renders, links to referenced components resolve, and descriptions align with the current codebase.
Escalate to: Architecture owner if component boundaries change or new services are added.
---

# System overview

ADE ships as a single Docker container bundling the frontend, FastAPI backend, deterministic processor, and storage dependencies. The goals are simple deployment, predictable behaviour, and audit-friendly operations. Understanding these building blocks is enough to reason about new integrations or configuration changes without reading through every backend module.

```
+----------------------------- Docker container -----------------------------+
|  React UI  ↔  FastAPI backend  ↔  Pure-Python processor helpers             |
|                                     |                                       |
|                                     ├─ SQLite database  (data/db/ade.sqlite) |
|                                     └─ Document storage (data/documents/)    |
+-----------------------------------------------------------------------------+
```

_A future diagram asset will live at `docs/assets/system-overview.png` once rendered from the architecture design._

## Components

- **Frontend (`frontend/`)** — React + Vite application for uploading documents, reviewing jobs, and managing configuration revisions. Consumes only the documented API surface.
- **Backend (`backend/app/`)** — FastAPI entry point with routes, services, authentication, and persistence helpers. Modules include:
  - `config.py` — Central settings loaded from `ADE_` environment variables.
  - `routes/` — HTTP endpoints for documents, configurations, jobs, events, health, and authentication.
  - `services/` — Deterministic helpers for documents, events, configurations, and maintenance tasks.
  - `auth/` — Password hashing, session management, and optional SSO utilities.
  - `maintenance/` — Scheduler and CLI tooling for document purge operations.
- **Processor (`backend/processor/`)** — Pure functions that detect tables, map columns, and emit audit notes without side effects.
- **Storage** — SQLite database (`data/db/ade.sqlite`) and filesystem-backed document store (`data/documents/`). Both paths mount as volumes in production to simplify backup.

## Integration surfaces

- **Configuration UI** — Preferred path for drafting, validating, and publishing configuration revisions. The UI calls the same REST endpoints documented for automation, but keeps guard rails (role checks, payload validation, event previews) in front of day-to-day users.
- **REST API** — Used by the UI and automation clients. Humans authenticate with Basic or SSO to receive a session cookie; service accounts send `Authorization: Bearer <API_KEY>` tokens that ADE verifies against the `api_keys` table.
- **Command-line helpers** — Targeted scripts (for example, `python -m backend.app.auth.manage`) handle administrative tasks that need direct database access or bulk operations.

These interfaces share the same event log and configuration versioning, ensuring architecture discussions can focus on system behaviour rather than transport differences.

## Job lifecycle

1. A document is uploaded via `POST /documents`, validated, and stored with metadata (`document_id`, checksums, `expires_at`).
2. ADE resolves the active configuration for the document type (`GET /configurations/active/{document_type}`) and records a job via `POST /jobs`.
3. Processor helpers execute deterministically using the referenced configuration payload.
4. Results (input metadata, output tables, metrics, audit notes) persist with the job record for replay.
5. Events emitted through `backend/app/services/events.py` capture job creation, status transitions, configuration activations, and document deletions.

Configuration changes typically originate in the UI, which records the same events as direct API calls. This keeps the job lifecycle stable regardless of whether the trigger was a human-operated publish or an automated promotion.

## Events and documents

- The immutable event log stored in the `events` table underpins auditing. Key families include `document.deleted`, `configuration.*`, and `job.status.*`.
- `/events` provides a paginated global feed, while entity-specific endpoints (`/documents/{id}/events`, `/jobs/{id}/events`, `/configurations/{id}/events`) return scoped timelines.
- Document retention policies and purge summaries surface on `GET /health` (see [Operations](../operations/README.md)).

## Where to go next

- Review [Authentication modes](../security/authentication-modes.md) to understand access controls, including the API key roadmap.
- Dive into [Configuration concepts](../configuration/concepts.md) for lifecycle specifics.
- Consult the [Environment variables reference](../reference/environment-variables.md) when preparing deployments.

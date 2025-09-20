---
Audience: Data teams
Goal: Summarise the REST API surface exposed today, including authentication requirements and key request/response shapes.
Prerequisites: API credentials (basic auth or session token) and access to the ADE deployment URL.
When to use: Start here when automating document ingestion, fetching job results, or wiring ADE into downstream systems.
Validation: Issue sample requests against `/health` and `/documents` (read-only) to confirm connectivity before integrating.
Escalate to: Platform administrators if endpoints respond unexpectedly or schema contracts change without notice.
---

# API overview

ADE exposes a single REST API implemented under `backend/app/routes/`. Endpoints require authentication unless the deployment runs in `ADE_AUTH_MODES=none`. This guide summarises the routes available today and how to exercise them while noting how the upcoming API key fits into the picture.

## Authentication roadmap

| Mode | Status | Typical usage |
| --- | --- | --- |
| API key header | **Planned.** Will issue a static secret per integration and expect a header such as `ADE-API-Key: <token>`. | Service accounts, scheduled exports, and partner integrations. |
| Session cookie | **Available today.** Authenticate once with HTTP Basic credentials and persist the returned cookie. | Browser UI and automation scripts until API keys ship. |

While API key support is under development, new integrations should still be written to inject a header so the switch is trivial once the feature lands. Use the session cookie flow as the temporary authentication step.

### Current session-based login

1. Call `POST /auth/login` with HTTP Basic credentials (see `backend/app/routes/auth.py`). ADE issues an opaque session token as an HttpOnly cookie.
2. Include the cookie on subsequent requests. Rotate credentials or log out via `POST /auth/logout` when done.
3. Refresh the session periodically by calling `POST /auth/refresh`.

Session semantics and environment toggles live in [Authentication modes](../security/authentication-modes.md).

### Prepare for the API key

Design clients to read an environment variable (for example, `ADE_API_KEY`) and attach it to every request once available:

```python
import os
import requests

headers = {
    "ADE-API-Key": os.environ["ADE_API_KEY"],
    "Content-Type": "application/json",
}
response = requests.get("https://ade.example.com/jobs", headers=headers, cookies=session_cookie)
```

Until ADE issues keys, leave the header absent and rely on the session cookie alone. No backend changes are required when the header becomes mandatory; clients simply start populating it.

## Documents (`backend/app/routes/documents.py`)

| Endpoint | Purpose | Auth | Key parameters |
| --- | --- | --- | --- |
| `POST /documents` | Upload a document for processing. Returns metadata with generated `document_id`. | Required | Multipart form with `file` (binary), optional `title`, `document_type`, and `expires_at` ISO 8601 timestamp. |
| `GET /documents` | List stored documents. Supports pagination and filtering. | Required | `limit`, `offset`, `document_type`, `include_deleted`. |
| `GET /documents/{document_id}` | Retrieve metadata for a single document. | Required | Path parameter `document_id` (ULID). |
| `GET /documents/{document_id}/download` | Stream the stored file. | Required | Path parameter `document_id`. |
| `DELETE /documents/{document_id}` | Soft-delete a document and record audit details. | Required | JSON body with `deleted_by` and optional `delete_reason`. |

The upload response references schemas defined in `backend/app/schemas.py` (`DocumentResponse`). Field definitions align with [ADE_GLOSSARY.md](../../ADE_GLOSSARY.md).

## Configurations (`backend/app/routes/configurations.py`)

Configurations govern how ADE processes documents.

| Endpoint | Purpose | Auth | Key parameters |
| --- | --- | --- | --- |
| `POST /configurations` | Create a draft or immediately active configuration revision. | Required | JSON body `document_type`, `title`, `payload`, optional `is_active`. |
| `GET /configurations` | List all configuration revisions (newest first). | Required | Pagination handled server-side; filter by document type client-side. |
| `GET /configurations/{configuration_id}` | Fetch a specific revision by ULID. | Required | Path parameter `configuration_id`. |
| `GET /configurations/active/{document_type}` | Resolve the active revision for a document type. | Required | Path parameter `document_type`. |
| `PATCH /configurations/{configuration_id}` | Update metadata or activate a revision. | Required | JSON body with fields from `ConfigurationUpdate` (see schemas). |
| `GET /configurations/{configuration_id}/events` | Timeline of configuration-related events. | Required | Query params: `limit`, `offset`, optional `event_type`, `source`, `request_id`, `occurred_before/after`. |

Use the [Publishing and rollback](../configuration/publishing-and-rollback.md) guide when orchestrating promotions.

## Jobs (`backend/app/routes/jobs.py`)

Jobs represent execution attempts against documents and configurations.

| Endpoint | Purpose | Auth | Key parameters |
| --- | --- | --- | --- |
| `POST /jobs` | Queue a job for processing. | Required | JSON body referencing `document_id`, optional `configuration_id` or `configuration_version`. |
| `GET /jobs` | List jobs with pagination. | Required | Query `limit`, `offset`, `document_type`, `status`. |
| `GET /jobs/{job_id}` | Inspect a single job, including input/output payloads. | Required | Path parameter `job_id`. |
| `PATCH /jobs/{job_id}` | Update a running job (status, outputs, metrics). | Required | JSON body following `JobUpdate` schema; rejected once job completes. |

## Events (`backend/app/routes/events.py`)

| Endpoint | Purpose | Auth | Key parameters |
| --- | --- | --- | --- |
| `GET /events` | Global immutable event feed. | Required | Query `limit`, `offset`, `entity_type`, `entity_id`, `event_type`, `source`, `request_id`, `occurred_before/after`. |
| `GET /documents/{document_id}/events` | Timeline for a specific document. | Required | Path `document_id`; same filters as above. |
| `GET /jobs/{job_id}/events` | Job-specific events. | Required | Path `job_id`. |

Events follow the canonical structure described in `backend/app/schemas.py` (`EventResponse`).

## Health (`backend/app/routes/health.py`)

- `GET /health` — Returns `{ "status": "ok" }` when the API, database, and purge scheduler are healthy. The response includes the latest purge summary under the `purge` key.

## Sample workflow

```bash
# 1. Authenticate and capture the session cookie
curl -i -c ade-cookie.txt -X POST \
  -u "admin@example.com:change-me" \
  https://ade.example.com/auth/login

# 2. Upload a document (expires in 7 days)
curl -b ade-cookie.txt -X POST \
  -F "file=@invoice.pdf" \
  -F "document_type=invoice" \
  -F "expires_at=$(date -u -d '+7 days' '+%Y-%m-%dT%H:%M:%SZ')" \
  https://ade.example.com/documents

# 3. Resolve the active configuration for the document type
curl -b ade-cookie.txt https://ade.example.com/configurations/active/invoice

# 4. Queue a job
curl -b ade-cookie.txt -X POST \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc_01H...", "document_type": "invoice"}' \
  https://ade.example.com/jobs

# 5. Inspect job status
curl -b ade-cookie.txt https://ade.example.com/jobs/job_2024_01_01_0001
```

If any call returns 401, refresh the session via `/auth/refresh` or repeat the login. Unexpected 5xx responses should be escalated with timestamp, request ID (from headers), and payload details.

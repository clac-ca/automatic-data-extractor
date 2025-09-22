---
Audience: Data teams
Goal: Summarise the REST API surface exposed today, including authentication requirements and key request/response shapes.
Prerequisites: API credentials (JWT bearer token, SSO access, or API key) and access to the ADE deployment URL.
When to use: Start here when automating document ingestion, fetching job results, or wiring ADE into downstream systems.
Validation: Issue sample requests against `/health` and `/documents` (read-only) to confirm connectivity before integrating.
Escalate to: Platform administrators if endpoints respond unexpectedly or schema contracts change without notice.
---

# API overview

ADE exposes a single REST API implemented under `backend/app/routes/`. Endpoints require authentication unless the deployment runs with `AUTH_DISABLED` or `ADE_AUTH_MODES=none`. This guide summarises the routes available today and shows how session cookies and API keys fit together.

## Authentication options

ADE offers three entry points for authenticated requests:

| Mode | Typical usage |
| --- | --- |
| `POST /auth/token` | Operators submitting email/password credentials. Returns a JWT for `Authorization: Bearer <token>`. |
| `/auth/sso/login` → `/auth/sso/callback` | Browser-based OIDC flows. The callback responds with the same JWT as the password endpoint. |
| API key (`X-API-Key`) | Automation clients that need non-interactive access. |

Bearer tokens and API keys drive the same authorisation checks across every router.

### Password login

```python
import requests

resp = requests.post(
    "https://ade.example.com/auth/token",
    data={"username": "admin@example.com", "password": "secret123"},
    timeout=10,
)
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
```

### SSO login

Direct a browser to `/auth/sso/login`. ADE handles the PKCE challenge, exchanges the authorisation code at the provider's token endpoint, and responds with the standard ADE bearer token from `/auth/sso/callback`. The frontend can then store the token client-side or relay it to downstream tooling.

### API key requests

```python
headers = {"X-API-Key": api_key}
response = requests.get("https://ade.example.com/jobs", headers=headers, timeout=10)
```

API keys are hashed at rest and track `last_seen` metadata automatically; no additional session state is required.

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
# 1. Authenticate and capture the bearer token
token=$(curl -s -X POST \
  -H "content-type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=change-me" \
  https://ade.example.com/auth/token | jq -r .access_token)

# 2. Upload a document (expires in 7 days)
curl -H "Authorization: Bearer ${token}" -X POST \
  -F "file=@invoice.pdf" \
  -F "document_type=invoice" \
  -F "expires_at=$(date -u -d '+7 days' '+%Y-%m-%dT%H:%M:%SZ')" \
  https://ade.example.com/documents

# 3. Resolve the active configuration for the document type
curl -H "Authorization: Bearer ${token}" https://ade.example.com/configurations/active/invoice

# 4. Queue a job
curl -H "Authorization: Bearer ${token}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"document_id": "doc_01H...", "document_type": "invoice"}' \
  https://ade.example.com/jobs

# 5. Inspect job status
curl -H "Authorization: Bearer ${token}" https://ade.example.com/jobs/job_2024_01_01_0001
```

If any call returns 401, obtain a fresh token or re-issue the API key. Unexpected 5xx responses should be escalated with timestamp, request ID (from headers), and payload details.

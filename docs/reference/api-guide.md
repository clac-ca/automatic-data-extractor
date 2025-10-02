# API Guide

This guide is for developers who want to integrate with the Automatic Data Extractor (ADE) directly through the HTTP API. It summarises authentication, core resources, and usage patterns so you can build reliable automations without reading the entire codebase.

## Base URL and versioning

ADE exposes a JSON REST API under a versioned base path:

- **Base URL**: `https://{your-domain}/api`
- **Current version**: `v1`
- **Example**: `https://ade.example.com/api/v1`

Future versions will follow the same resource model. When breaking changes are required, a new version path (for example `/api/v2`) will be introduced.

## Authentication

ADE uses bearer tokens issued by the administrator of your workspace.

1. Request a token via the admin console or service account provisioning flow.
2. Send the token in the `Authorization` header: `Authorization: Bearer <token>`.
3. Tokens are scoped to a single workspace. Include the workspace ULID in the URL path for scoped routes, e.g. `/workspaces/{workspace_id}/...`.

Requests without valid tokens receive HTTP `401 Unauthorized` responses. If the token is valid but lacks permissions for a resource you will receive `403 Forbidden`.

## Core resources

### Documents

Upload source files for extraction. All document routes are nested under the workspace path segment.

- `POST /workspaces/{workspace_id}/documents` – multipart upload endpoint.
- `GET /workspaces/{workspace_id}/documents/{document_id}` – fetch metadata, including upload timestamps and submitter.
- `DELETE /workspaces/{workspace_id}/documents/{document_id}` – remove a document and any derived results, if permitted.

### Jobs

Trigger and monitor extraction runs.

- `POST /workspaces/{workspace_id}/jobs` – start an extraction by referencing an existing `document_id` or by including a file upload in the request.
- `GET /workspaces/{workspace_id}/jobs/{job_id}` – retrieve status (`queued`, `processing`, `succeeded`, `failed`) and progress metrics.
- `GET /workspaces/{workspace_id}/jobs` – list recent jobs, filterable by status, document, or submitter using query parameters.

### Results

Retrieve structured tables produced by completed jobs.

- `GET /workspaces/{workspace_id}/jobs/{job_id}/tables` – list extracted tables linked to a job.
- `GET /workspaces/{workspace_id}/jobs/{job_id}/tables/{table_id}` – retrieve a single extracted table record.
- `GET /workspaces/{workspace_id}/documents/{document_id}/tables` – list tables derived from a document.

### Events

Track the immutable audit trail for compliance and debugging.

- `GET /workspaces/{workspace_id}/events` – stream ordered events within a workspace.
- `GET /workspaces/{workspace_id}/events/{event_id}` – inspect a single event, including actor, timestamp, and payload snapshot.

## Error handling

ADE follows standard HTTP semantics and FastAPI's default error envelope. Every non-2xx response returns a JSON document with a `detail` field:

- For most validation, authentication, and permission failures the `detail` value is a string describing the problem (for example `"Authentication required"` or `"Workspace slug already in use"`).
- Some operations include structured details for easier automation. Job submission failures return `{"detail": {"error": "job_failed", "job_id": "...", "message": "..."}}`, while job result lookups that are still pending return `{"detail": {"error": "job_results_unavailable", "job_id": "...", "status": "processing", "message": "..."}}`.

Use the HTTP status code to drive retry behaviour—`5xx` and `429` responses merit exponential backoff, whereas `4xx` errors require user action before retrying. Validation errors (`422`) and conflict responses (`409`) intentionally provide enough context in the `detail` payload to help clients resolve the issue.

## Webhooks and callbacks

If you need near real-time updates, register a webhook endpoint with the ADE team. Webhooks fire on job completion, failure, and manual review events. Delivery includes an HMAC signature header so you can verify authenticity.

## SDKs and client libraries

Official client libraries are on the roadmap. Until they ship, use your preferred HTTP client. The API uses predictable JSON schemas, making it easy to generate typed clients with tools such as OpenAPI Generator once the schema is published.

## Sandbox environment

For integration testing, ADE provides a sandbox deployment with seeded workspaces and sample documents. Contact support to receive credentials. Sandbox data resets daily, so do not store production information there.

## Support

If you encounter issues or need new API capabilities, reach out through the developer support channel listed in your onboarding pack. Provide request IDs and timestamps when reporting problems to help the team diagnose them quickly.

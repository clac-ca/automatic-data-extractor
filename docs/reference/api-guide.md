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
3. Tokens are scoped to a single workspace. Include the workspace ULID in endpoints that require it (see below).

Requests without valid tokens receive HTTP `401 Unauthorized` responses. If the token is valid but lacks permissions for a resource you will receive `403 Forbidden`.

## Core resources

### Documents

Upload source files for extraction.

- `POST /documents/` – multipart upload endpoint. Include `workspace_id`, `filename`, and the file payload.
- `GET /documents/{document_id}` – fetch metadata, including upload timestamps and submitter.
- `DELETE /documents/{document_id}` – remove a document and any derived results, if permitted.

### Jobs

Trigger and monitor extraction runs.

- `POST /jobs/` – start an extraction by referencing an existing `document_id` or by including a file upload in the request.
- `GET /jobs/{job_id}` – retrieve status (`queued`, `processing`, `completed`, `needs_attention`) and progress metrics.
- `GET /jobs/?workspace_id=...` – list recent jobs, filterable by status, document, or submitter.

### Results

Retrieve structured tables produced by completed jobs.

- `GET /results/{result_id}` – return table metadata, column definitions, and checksums.
- `GET /results/{result_id}/download` – download the extracted table as CSV or Excel by setting the `format` query parameter.
- `GET /documents/{document_id}/results` – list results linked to a document.

### Events

Track the immutable audit trail for compliance and debugging.

- `GET /events/` – stream ordered events within a workspace.
- `GET /events/{event_id}` – inspect a single event, including actor, timestamp, and payload snapshot.

## Error handling

ADE follows standard HTTP semantics. When a request fails, the response includes:

- `status` – HTTP status code (e.g., `400`, `404`, `500`).
- `code` – ADE-specific error identifier for programmatic handling.
- `message` – human-readable description of what went wrong.
- `details` – optional field containing validation errors or contextual information.

Implement retry logic for `429 Too Many Requests` and `5xx` status codes with exponential backoff. Validation errors (`422`) should be fixed before retrying.

## Webhooks and callbacks

If you need near real-time updates, register a webhook endpoint with the ADE team. Webhooks fire on job completion, failure, and manual review events. Delivery includes an HMAC signature header so you can verify authenticity.

## SDKs and client libraries

Official client libraries are on the roadmap. Until they ship, use your preferred HTTP client. The API uses predictable JSON schemas, making it easy to generate typed clients with tools such as OpenAPI Generator once the schema is published.

## Sandbox environment

For integration testing, ADE provides a sandbox deployment with seeded workspaces and sample documents. Contact support to receive credentials. Sandbox data resets daily, so do not store production information there.

## Support

If you encounter issues or need new API capabilities, reach out through the developer support channel listed in your onboarding pack. Provide request IDs and timestamps when reporting problems to help the team diagnose them quickly.

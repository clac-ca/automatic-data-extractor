# Documents API Reference

## Purpose

Document endpoints for document upload, metadata management, tagging, comments, views, and content retrieval.

## Authentication Requirements

All document endpoints are protected and require workspace document permissions.

## Endpoint Matrix

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents` | protected | `200` | path + cursor/search/filter | cursor page of document rows | `401`, `403` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents` | protected | `201` | path + multipart (`file`, optional `metadata`, `run_options`, `conflictMode`) | document record | `400`, `401`, `403`, `409`, `413`, `429` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/batch/delete` | protected | `200` | path + JSON `documentIds` | batch delete response | `400`, `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/batch/restore` | protected | `200` | path + JSON `documentIds` | batch restore response | `400`, `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/batch/tags` | protected | `200` | path + JSON add/remove tags | batch tag response | `400`, `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/delta` | protected | `200` | path + token/limit query | delta changes payload | `400`, `401`, `403` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/stream` | protected | `200` | path + optional cursor query | SSE stream | `401`, `403` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/tags` | protected | `200` | path + paging query | tag catalog page | `401`, `403` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/views` | protected | `200` | path + pagination query | saved view list | `401`, `403` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/views` | protected | `201` | path + JSON view create payload | saved view record | `400`, `401`, `403`, `409` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}/documents/views/{viewId}` | protected | `200` | path + JSON view patch | saved view record | `400`, `401`, `403`, `404`, `409` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}/documents/views/{viewId}` | protected | `204` | path | empty | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}` | protected | `200` | path | document record | `401`, `403`, `404` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}` | protected | `200` | path + JSON patch | document record | `400`, `401`, `403`, `404`, `409` |
| `DELETE` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}` | protected | `204` | path | empty | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/comments` | protected | `200` | path + pagination query | comment page | `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/comments` | protected | `201` | path + JSON comment payload | comment record | `400`, `401`, `403`, `404`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/download` | protected | `200` | path | file stream | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/listrow` | protected | `200` | path | document list-row projection | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/original/download` | protected | `200` | path | original file stream | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/preview` | protected | `200` | path + sheet preview query | workbook preview payload | `401`, `403`, `404`, `415`, `422` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/restore` | protected | `200` | path | restored document record | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/sheets` | protected | `200` | path | sheet list payload | `401`, `403`, `404`, `415`, `422` |
| `PUT` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/tags` | protected | `200` | path + JSON full tag set | document record | `400`, `401`, `403`, `404` |
| `PATCH` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/tags` | protected | `200` | path + JSON add/remove tags | document record | `400`, `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/versions` | protected | `201` | path + multipart file/version fields | document record | `400`, `401`, `403`, `404`, `413`, `409` |
| `GET` | `/api/v1/workspaces/{workspaceId}/documents/{documentId}/versions/{versionNo}/download` | protected | `200` | path | specific version stream | `401`, `403`, `404` |

## Core Endpoint Details

### `POST /api/v1/workspaces/{workspaceId}/documents`

- Multipart upload endpoint used by API integrations and the web upload workflow.
- `run_options` accepts JSON string values with API keys:
  - `activeSheetOnly`
  - `inputSheetNames`
- `activeSheetOnly` and `inputSheetNames` are mutually exclusive in one request.

### `GET /api/v1/workspaces/{workspaceId}/documents`

- Primary endpoint for verifying upload outcomes and checking `lastRun` metadata.
- Supports filtering, search, pagination, and sorting.

### `POST /api/v1/workspaces/{workspaceId}/documents/{documentId}/versions`

- Uploads a new version for an existing document identity.
- Use this when replacing file content while preserving document metadata history.

## Error Handling

- `400 Bad Request`: invalid JSON metadata/run options or invalid filters.
- `401 Unauthorized`: missing/invalid auth credentials.
- `403 Forbidden`: workspace permissions missing.
- `404 Not Found`: workspace/document/view/version not found.
- `409 Conflict`: naming/state conflicts for uploads or restores.
- `413 Content Too Large`: upload exceeds configured size limit.
- `415 Unsupported Media Type`: preview/sheet introspection not supported for file type.
- `422 Unprocessable Content`: document parse or validation errors.
- `429 Too Many Requests`: upload concurrency/rate limits.

See [Errors and Problem Details](errors-and-problem-details.md) for shared response format.

## Related Guides

- [Upload a Document and Queue Runs](../../how-to/api-upload-and-queue-runs.md)

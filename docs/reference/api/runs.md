# Runs API Reference

## Purpose

Document run creation, monitoring, events, and output retrieval endpoints.

## Authentication Requirements

All run endpoints are protected and scoped to workspace run permissions.

## Endpoint Matrix

| Method | Path | Auth | Primary status | Request shape | Response shape | Common errors |
| --- | --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs` | protected | `200` | path + cursor/search/filter | cursor page of runs | `401`, `403` |
| `POST` | `/api/v1/workspaces/{workspaceId}/runs` | protected | `201` | path + JSON run create payload | run resource | `400`, `401`, `403`, `404`, `409`, `422` |
| `POST` | `/api/v1/workspaces/{workspaceId}/runs/batch` | protected | `201` | path + JSON batch payload | batch run response | `401`, `403`, `404`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}` | protected | `200` | path | run resource | `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/cancel` | protected | `200` | path | run resource | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/columns` | protected | `200` | path + optional column filters | list of run column rows | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/events/download` | protected | `200` | path | NDJSON stream | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/events/stream` | protected | `200` | path + optional `cursor` | SSE stream | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/fields` | protected | `200` | path | list of run field rows | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/input` | protected | `200` | path | run input metadata | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/input/download` | protected | `200` | path | input file stream | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/metrics` | protected | `200` | path | run metrics payload | `401`, `403`, `404` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/output` | protected | `200` | path | output metadata | `401`, `403`, `404` |
| `POST` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/output` | protected | `201` | path + multipart output file | output metadata | `401`, `403`, `404`, `409`, `413` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/output/download` | protected | `200` | path | output file stream | `401`, `403`, `404`, `409` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/output/preview` | protected | `200` | path + preview query | worksheet preview payload | `401`, `403`, `404`, `409`, `415`, `422` |
| `GET` | `/api/v1/workspaces/{workspaceId}/runs/{runId}/output/sheets` | protected | `200` | path | output sheet list | `401`, `403`, `404`, `409`, `415`, `422` |

## Core Endpoint Details

### `POST /api/v1/workspaces/{workspaceId}/runs`

- Creates and queues one run for one input document.
- Optional `options` controls behavior (`activeSheetOnly`, `inputSheetNames`, operation mode).

### `GET /api/v1/workspaces/{workspaceId}/runs/{runId}`

- Primary polling endpoint for run status transitions.
- Use with events endpoints for live updates.

### `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/events/stream`

- SSE event stream for real-time run updates.
- Resume from known stream offset using `cursor` or `Last-Event-ID`.

### `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/output/download`

- Downloads produced output when run output is available.
- Returns conflict/availability errors while output is not ready.

## Error Handling

- `401 Unauthorized`: missing/invalid auth credentials.
- `403 Forbidden`: workspace run permission missing.
- `404 Not Found`: workspace/run/input/output not found.
- `409 Conflict`: run not cancellable or output not ready.
- `413 Content Too Large`: uploaded manual output exceeds limit.
- `415 Unsupported Media Type`: worksheet features unavailable for output type.
- `422 Unprocessable Content`: run output parsing/preview failures.

See [Errors and Problem Details](errors-and-problem-details.md) for shared response format.

## Related Guides

- [Create and Monitor Runs](../../how-to/api-create-and-monitor-runs.md)

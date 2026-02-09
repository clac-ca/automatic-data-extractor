# Operate Runs

## Goal

Monitor run processing and resolve run issues in production.

## Quick Definitions

- **Run**: one processing attempt for one input document.
- **Queue**: runs waiting for worker execution.
- **Lease**: temporary claim that prevents duplicate processing.

## Run Flow

1. run is created
2. status becomes `queued`
3. worker claims run, status becomes `running`
4. worker writes output and event log
5. status becomes `succeeded` or `failed`

## Monitor Activity (Production)

Single-container app logs:

```bash
az containerapp logs show --name ade-app --resource-group <resource-group> --follow
```

Local development fallback:

```bash
docker compose logs -f app
docker compose logs -f worker
```

## Useful Run Endpoints

- `GET /api/v1/workspaces/{workspaceId}/runs/{runId}`
- `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/events/stream`
- `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/events/download`
- `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/output`
- `GET /api/v1/workspaces/{workspaceId}/runs/{runId}/output/download`

## Event Log Location

Uploaded run event log path:

- `<workspace_id>/runs/<run_id>/logs/events.ndjson`

## If Runs Keep Failing

- inspect app logs for worker/runtime errors
- verify at least one healthy replica is running
- verify retries/timeouts in [Runtime Lifecycle](../reference/runtime-lifecycle.md)
- tune capacity with [Scale and Tune Throughput](scale-and-tune-throughput.md)

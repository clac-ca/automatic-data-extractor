# ADE API Service

This directory contains the FastAPI application that powers ADE. Install it in editable mode during development:

```bash
pip install -e apps/ade-api[dev]
```

See the repository root `README.md` for full setup instructions.

## Config scaffolding

The API no longer bundles or syncs template folders. When you create a configuration from the UI/API, it shells out to the ade-engine CLI:

- `ade-engine config init <workspace>/<config_id>` – lays down the built-in starter template that ships with the engine package.
- `ade-engine config validate --config-package <path>` – checks that the generated/edited package imports and registers correctly.

Configurations are still stored under `./data/workspaces/{workspace_id}/config_packages/{config_id}/` by default, and you can clone/import existing configs as before. The create-configuration API supports `source.type="template"` (engine starter template) and `source.type="clone"` (copy an existing configuration).

## Logging

- The API uses a console formatter with correlation IDs: `2025-11-27T03:05:00.302Z INFO  ade_api.features.runs.service [cid=abcd1234] run.create.success workspace_id=... run_id=...`
- Set `ADE_LOGGING_LEVEL=DEBUG` to see debug logs from services; default is `INFO`. Example: `ADE_LOGGING_LEVEL=DEBUG ade dev --backend-only`.
- Request logs include the `X-Request-ID` correlation ID and request metadata; global exception handlers log unexpected errors and 5xx `HTTPException`s.
- Attach domain IDs via `extra=log_context(...)` when logging (workspace/config/build/run/document/user IDs).

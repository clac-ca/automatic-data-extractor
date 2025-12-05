# ADE API Service

This directory contains the FastAPI application that powers ADE. Install it in editable mode during development:

```bash
pip install -e apps/ade-api[dev]
```

See the repository root `README.md` for full setup instructions.

## Bundled config templates

The API ships with two installable `ade_config` templates under `src/ade_api/templates/config_packages/`:

- **default** – mirrors the reference manifest shape described in `apps/ade-engine/docs/02-config-and-manifest.md` and includes the detectors/hooks used in engine integration tests.
- **sandbox** – a minimal smoke-test template that matches the engine end-to-end fixtures (row + column detectors, a simple note hook, and a v1 manifest with relative module paths).

On startup the API copies bundled templates from `ADE_CONFIG_TEMPLATES_SOURCE_DIR` (defaults to the packaged `src/ade_api/templates/config_packages`) into `ADE_CONFIG_TEMPLATES_DIR` (defaults to `./data/templates/config_packages`). Bundled template folders are replaced on each start; any additional user-provided templates left under `ADE_CONFIG_TEMPLATES_DIR` are preserved.

You can materialize either template through the `ConfigurationsService` endpoint when creating a configuration:

```http
POST /api/v1/workspaces/{workspace_id}/configurations
{
  "display_name": "Sandbox Config",
  "source": {
    "type": "template",
    "template_id": "sandbox"
  }
}
```

The backend copies the requested template into `./data/workspaces/{workspace_id}/config_packages/{config_id}/`, ready for editing and activation. After activation, runs will build a virtual environment for the template and execute the engine with the manifest and detectors bundled in that directory. Use the **sandbox** template for a quick start on new environments; switch to **default** when you need the fuller set of detectors demonstrated in the engine docs.

## Logging

- The API uses a console formatter with correlation IDs: `2025-11-27T03:05:00.302Z INFO  ade_api.features.runs.service [cid=abcd1234] run.create.success workspace_id=... run_id=...`
- Set `ADE_LOGGING_LEVEL=DEBUG` to see debug logs from services; default is `INFO`. Example: `ADE_LOGGING_LEVEL=DEBUG ade dev --backend-only`.
- Request logs include the `X-Request-ID` correlation ID and request metadata; global exception handlers log unexpected errors and 5xx `HTTPException`s.
- Attach domain IDs via `extra=log_context(...)` when logging (workspace/config/build/run/document/user IDs).

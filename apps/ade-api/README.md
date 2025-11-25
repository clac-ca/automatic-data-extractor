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

You can materialize either template through the `ConfigurationsService` endpoint when creating a configuration:

```http
POST /api/v1/workspaces/{workspace_id}/configs
{
  "display_name": "Sandbox Config",
  "source": {
    "type": "template",
    "template_id": "sandbox"
  }
}
```

The backend copies the requested template into `./data/workspaces/{workspace_id}/config_packages/{config_id}/`, ready for editing and activation. After activation, runs will build a virtual environment for the template and execute the engine with the manifest and detectors bundled in that directory. Use the **sandbox** template for a quick start on new environments; switch to **default** when you need the fuller set of detectors demonstrated in the engine docs.

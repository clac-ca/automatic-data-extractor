# Config Builder Streaming Integration Plan (Deprecated)

This plan assumed dedicated build streaming endpoints. Build orchestration has
been removed from the API, and the workbench now consumes **run** streams only.

Current guidance:

- Use `/api/v1/runs/{runId}/events/stream` for console output.
- Environment provisioning is worker-owned and does not have a public streaming
  endpoint in v1.
- See `apps/ade-web/docs/09-workbench-editor-and-scripting.md` for the
  up-to-date workbench behavior.

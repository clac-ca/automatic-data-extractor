# Frontend Integration Notes for ADE Runs

This audit catalogs the React surfaces that need to adopt the new runs API
before the feature can ship end-to-end. Review this document alongside
`docs/ade_runs_api_spec.md`, `docs/reference/config_builder_streaming_plan.md`,
and WP12 when planning the UI work.

## Workspace Documents screen

The documents screen already references "runs" in copy and state but still
relies on the legacy runs endpoints. Key touchpoints:

- `apps/ade-web/src/screens/Workspace/sections/Documents/index.tsx`
  - `DocumentRunsDrawer` keeps run drawer state in `document_runs` storage
    keys and displays the "Run" button per document. Update the request
    handlers to call `POST /api/v1/configurations/{configuration_id}/runs` and stream
    events into the console once the backend is wired up.
  - `useDocumentRunsQuery` (search for `runsQuery`) polls the runs router
    to show historical runs. Replace it with the new runs log endpoint and
    add pagination/`after_id` handling.
  - The "Safe mode" tooltips gate run buttons. Surface the new run status
    states (queued, running, succeeded, failed, canceled) and error
    messaging in the drawer summary.

## Config Builder panel (Terminal | Run | Problems)

- `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/` now
  consumes run/build NDJSON streams: `Terminal` shows raw logs, `Problems`
  shows validation issues, and `Run` hosts summary/output/telemetry cards.
- `BottomPanel.tsx` already accepts console lines with `origin` and supports
  origin/level filters, follow toggle, and clear. Keep feeding it build/run
  events via `describeRunEvent`/`describeBuildEvent`.
- `Workbench.tsx` keeps `validationState.status/lastRunAt` and the latest run
  summary. Ensure these hydrate from the streaming runs endpoints and the
  follow-up fetches (`fetchRunOutputs`, `fetchRunSummary`, `fetchRunTelemetry`).
- The chrome "Last run" pill opens the `Run` tab; the primary action is labeled
  **Test run**. Update any onboarding or inline help to reflect the new naming.

## Generated API types

Once the backend endpoints are available, run `ade openapi-types`
to regenerate `apps/ade-web/src/generated-types/openapi.d.ts` and add curated
schema exports under `apps/ade-web/src/schema/`. Update the React hooks to use
those types instead of ad-hoc interfaces.

## Follow-up work items

- Draft WP13 for the frontend implementation so the UI changes ship with a
  dedicated checklist.
- Coordinate with design on how to present streaming log output within the
  existing drawers and bottom console.

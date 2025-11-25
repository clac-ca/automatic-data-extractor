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
    handlers to call `POST /api/v1/configs/{config_id}/runs` and stream
    events into the console once the backend is wired up.
  - `useDocumentRunsQuery` (search for `runsQuery`) polls the runs router
    to show historical runs. Replace it with the new runs log endpoint and
    add pagination/`after_id` handling.
  - The "Safe mode" tooltips gate run buttons. Surface the new run status
    states (queued, running, succeeded, failed, canceled) and error
    messaging in the drawer summary.

## Config Builder validation console

- `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/` –
  validation actions dispatch `validateConfiguration` and display
  "Console streaming endpoints are not available yet." Replace this guard
  with a streaming client that consumes NDJSON events so the console shows
  live detector output.
- `Workbench.tsx` and `BottomPanel.tsx` track `validationState.status` and
  `lastRunAt`. Ensure these fields read from the new runs endpoints rather
  than the legacy validation responses.

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

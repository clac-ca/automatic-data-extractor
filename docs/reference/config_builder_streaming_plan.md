# Config Builder Streaming Integration Plan

This plan extends WP12 and the ADE builds/runs specs to document how the
config editor workbench should consume the new streaming endpoints.
Review this file alongside `docs/ade_runs_api_spec.md`,
`docs/ade_builds_api_spec.md`, and `docs/ade_builds_streaming_plan.md`
before making UI changes.

## Goals

- Surface `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/builds`
and `POST /api/v1/configs/{config_id}/runs` streaming output inside the
config builder console.
- Keep validation messaging in the secondary panel while adding
real-time console updates for build/run events.
- Reuse a shared NDJSON client so builds and runs follow the same
transport primitives.
- Preserve existing persistence of console panel state, including height
and collapsed preferences.

## Non-goals

- Replacing the legacy validation API (keep using it for structured
issues until runs expose equivalent payloads).
- Implementing document-level run triggers (covered by the documents
screen work).
- Changing backend behavior beyond consuming the streaming APIs.

## Implementation Outline

1. **Streaming primitives**
   - Add a small NDJSON reader utility that wraps `fetch` responses.
   - Create typed adapters for build and run events so UI code can
     iterate over strongly-typed objects.

2. **Workbench console state**
   - Promote console lines to React state instead of relying solely on
     seed data.
   - Provide helpers to append new lines with timestamps and cap the
     history length (~400 rows) to avoid uncontrolled growth.

3. **Event formatting**
   - Map build/run events to the existing `WorkbenchConsoleLine` shape.
     Success/failure events should render with `success`/`error` levels,
     stderr logs map to `warning`, and stdout logs to `info`.
   - Add unit tests covering the formatter so future schema tweaks only
     require updating one module.

4. **User actions**
   - Add a "Build environment" action next to "Run validation" that
     calls the streaming build endpoint with `{ stream: true }`.
   - Update the validation handler to kick off a streaming run (using
     `validate_only: true`) while still invoking the existing validation
     mutation for structured issues.
   - Ensure both actions open the console pane and switch to the
     "Console" tab automatically.

5. **Error handling & UX polish**
   - Catch `ApiError` and aborted fetches; append error messages to the
     console and surface a transient toast/notice in the workbench
     chrome.
   - When operations finish, drop a succinct summary line (status,
     exit code) and show a brief inline notice so users notice the
     outcome even if the console is collapsed.

6. **Documentation & tracking**
   - Link this plan from WP12 and the frontend integration notes.
   - Record decision log entries when the implementation lands so future
     agents know the console now expects NDJSON streams.

## Follow-ups

- Consider persisting console transcripts per configuration once we have
backend log pagination wired up for the UI.
- Evaluate whether we should surface background builds/runs in the
workbench when they are triggered elsewhere (polling + notifications).
- Add a cancel action once the backend exposes run/build cancellation
endpoints.

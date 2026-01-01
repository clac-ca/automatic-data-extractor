# Config Builder Streaming Integration Plan

This plan extends WP12 and the ADE builds/runs specs to document how the
config editor workbench should consume the new streaming endpoints.
Review this file alongside `docs/ade_runs_api_spec.md`,
`docs/ade_builds_api_spec.md`, and `docs/ade_builds_streaming_plan.md`
before making UI changes.

## Goals

- Surface `POST /api/v1/workspaces/{workspaceId}/configurations/{configurationId}/builds`
and `POST /api/v1/configurations/{configurationId}/runs` streaming output inside the
workbench panel (Terminal tab).
- Keep validation messaging in the `Problems` tab while adding real-time
console updates for build/run events.
- Use the shared NDJSON client so builds and runs follow the same transport
primitives and attach origin/level metadata for filtering.
- Preserve existing persistence of panel state, including height and collapsed
preferences.

## Non-goals

- Replacing the current validation API (keep using it for structured
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
   - Console lines are React state with capped history (~400 rows).
   - Lines include `origin` (`run`/`build`/`raw`) and `level` so UI filters
     can render Terminal like a real log viewer.

3. **Event formatting**
   - Map build/run events to the existing `WorkbenchConsoleLine` shape.
     Success/failure events should render with `success`/`error` levels,
     stderr logs map to `warning`, and stdout logs to `info`.
   - Add unit tests covering the formatter so future schema tweaks only
     require updating one module.

4. **User actions**
   - "Run validation" triggers a streaming run (`validate_only: true`) and
     still invokes the validation mutation for structured issues in Problems.
- "Test run" triggers a streaming extraction; when complete, the chrome pill
  and the `Run` tab surface outputs and event logs.
   - Both actions open the panel and focus the `Terminal` tab by default.

5. **Error handling & UX polish**
   - Catch `ApiError` and aborted fetches; append error messages to the
     console and surface a transient toast/notice in the workbench chrome.
- When operations finish, append a succinct status line (status/duration)
     and update the chrome "Last run" pill so users notice outcomes even if the
     panel is collapsed.

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

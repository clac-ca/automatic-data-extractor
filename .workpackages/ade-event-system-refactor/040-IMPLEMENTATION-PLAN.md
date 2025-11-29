# Implementation Plan - ADE Event System

This is the concrete plan for replacing v1 with the new unified event system.

There is **no backward compatibility** requirement. Part of this work is to remove v1 code and ensure nothing references the old events or streaming paths.

---

## Current code reference map (hotspots to change)

- ade-api run endpoints: `apps/ade-api/src/ade_api/features/runs/router.py` (`create_run_endpoint`, `get_run_events_endpoint`); all streaming today is NDJSON via `RunStreamFrame`.
- ade-api run orchestration: `apps/ade-api/src/ade_api/features/runs/service.py` (`stream_run`, `_stream_engine_run`, `_append_log`, `get_run_events`, `RunSummaryV1` rebuild); reads/writes `logs/events.ndjson`.
- ade-api build endpoints: `apps/ade-api/src/ade_api/features/builds/router.py` and `.../service.py` (`stream_build`, `_stream_build_process`, NDJSON `build.console`).
- ade-api tests that assert old event types: `apps/ade-api/tests/unit/features/runs/test_runs_service.py`.
- ade-engine docs describing v1 events: `apps/ade-engine/docs/11-ade-event-model.md` (mentions `run.console`/`build.console`).
- Frontend console/event helpers using v1 types: `apps/ade-web/src/screens/Workspace/sections/ConfigBuilder/workbench/utils/console.ts` and `.../utils/__tests__/console.test.ts`; docs at `apps/ade-web/docs/04-data-layer-and-backend-contracts.md`.

---

## Phase 1 - Shared types and envelope

**Goal:** Introduce canonical event envelope and payload models in ade-api and ade-engine.

**Tasks**

- Add `AdeEvent` envelope models shared across ade-api and ade-engine (Pydantic dataclasses for Python).
- Add typed payload models for:
  - `build.*`, `run.*`, `console.line`, `run.table.summary`, `run.validation.summary`, `run.error`.
- Replace ad-hoc dicts for events with these models (where feasible) to catch schema drift early.

---

## Phase 2 - Event dispatcher and NDJSON logging (ade-api)

**Goal:** Centralize all event emission.

**Tasks**

- Implement `emit_event(...)` helper in ade-api:
  - Accepts `type`, `source`, `run_id`, `build_id?`, `payload`.
  - Fetches workspace/config IDs from DB context.
  - Allocates per-`run_id` `sequence` (monotonic).
  - Generates `event_id`, `created_at`.
  - Writes to NDJSON (`events.ndjson`) under `runs/{run_id}/logs`.
  - Fan-out to in-memory subscribers (for SSE streaming).
- Implement `RunEventLogReader` for replay and summary building.

---

## Phase 3 - Replace streaming and run routes with new SSE-based design

**Goal:** Make the new API design (see `030-API-DESIGN-RUNS-AND-BUILDS.md`) the default, replacing v1.

**Tasks**

- Update existing run routes to match the new semantics:
  - `POST /workspaces/{w}/configurations/{c}/runs`:
    - Accepts JSON run request.
    - Creates run and build.
    - `stream=true` -> SSE streaming of AdeEvents.
    - `stream=false` -> JSON `{run_id, status}`.
- Implement SSE handler for:
  - `POST .../runs?stream=true` (create and stream).
  - `GET .../runs/{run_id}/events?stream=true`.
- Ensure both endpoints use the central event dispatcher subscription.

---

## Phase 4 - Integrate build orchestration with new events

**Goal:** Build operations use the new events and produce build logs as `console.line`.

**Tasks**

- In ade-api's build orchestration:
  - Emit `build.created`, `build.started`, `build.phase.started` / `build.phase.completed`, and `build.completed` via `emit_event`.
- Wrap pip/venv/config-install subprocesses with stream readers:
  - For each subprocess:
    - Capture stdout/stderr.
    - Convert lines to `console.line` events with `scope:"build"`.
    - See `090-CONSOLE-LOGGING.md` for helper shape.
- Update existing build streaming behavior:
  - Replace v1 NDJSON streaming with SSE:
    - `POST /.../builds?stream=true` -> SSE of `build.*` + `console.line` (scope:"build").
  - Ensure event shapes match the canonical payloads defined in `020-EVENT-TYPES-REFERENCE.md`.

---

## Phase 5 - Integrate run orchestration and engine subprocess

**Goal:** Runs have unified build and run event streams; engine output is translated into AdeEvents.

**Tasks**

- In run worker (ade-api):
  - Launch engine subprocess in the virtualenv.
  - For its stdout/stderr:
    - Use `read_stream_lines` helper (see `090-CONSOLE-LOGGING.md`) to:
      - Parse JSON lines with a `type` field -> treat as structured engine events.
      - Wrap non-JSON lines as `console.line` with `scope:"run"`.
- Ensure engine emits:
  - `run.phase.started`, `run.phase.completed`.
  - `run.table.summary`.
  - `run.validation.summary`.
  - Optional `run.validation.issue`.
  - Optional `run.error` where appropriate.
- Make sure the orchestrator:
  - Emits `run.queued`, `build.*`, `run.started`, and final `run.completed`.
  - Emits the banner `console.line` after build completion and before run start.

---

## Phase 6 - RunSummaryBuilder and canonical `run.completed`

**Goal:** Canonical summary for runs, and `run.completed` as the single source of truth.

**Tasks**

- Implement `RunSummaryBuilder` in ade-api:
  - Input: `RunEventLogReader` for a given `run_id`.
  - Output: `RunSummary` object (structure from `020-EVENT-TYPES-REFERENCE.md`).
  - Logic:
    - Read events in order.
    - Aggregate:
      - Core run timings and status.
      - Build env info.
      - Table and validation aggregates.
- Integrate into run finalization:
  - After engine subprocess completes:
    - Run `RunSummaryBuilder`.
    - Emit canonical `run.completed` via `emit_event`.
    - Update `runs` table with `status`, `exit_code`, `started_at`, `completed_at`, `summary_json`.
- Ensure only **one** `run.completed` is ever emitted per run.

---

## Phase 7 - ade-engine event emission adjustments

**Goal:** Engine emits structured events that ade-api can consume and wrap cleanly.

**Tasks**

- Add a simple `emit_event(type, payload)` helper in ade-engine that:
  - Fills `source:"engine"`.
  - Fills `run_id`, `workspace_id`, `configuration_id`, `build_id` from env/RunContext.
  - Writes **one JSON object per line** to stdout (engine NDJSON).
- Update engine to emit:
  - `run.phase.started`, `run.phase.completed`.
  - `run.table.summary`, `run.validation.summary`, `run.validation.issue`.
  - `run.error` when appropriate.
- Ensure engine **does not** emit a public `run.started` or `run.completed`; those are owned by ade-api.

---

## Phase 8 - ade-web UI updates

**Goal:** Config builder console and related UI use the new run stream.

**Tasks**

- Update config builder to:
  - Use `POST /.../runs?stream=true` for run execution.
  - Fallback to `GET /.../runs/{run_id}/events?stream=true` when reattaching.
- Rendering:
  - Show:
    - Build phases from `build.*`.
    - Run phases from `run.phase.*`.
    - Logs from `console.line`, grouped by `scope` and optionally by `phase`.
    - Summary states based on `run.completed`.
- Remove old NDJSON/`build.console`/`run.console` specific logic.

---

## Phase 9 - Cleanup and removal of v1

**Goal:** Ensure no traces of the old event system remain.

**Tasks**

- Remove:
  - v1 event types from ade-api and ade-engine.
  - v1 build stream codepaths that emit `build.console` and v1 event shapes.
  - v1 run streaming paths that forward engine events as-is.
  - Any frontend code referencing v1 event shapes or endpoint semantics.
- Add tests:
  - Unit tests for event dispatcher, `RunSummaryBuilder`, and console streaming helpers.
  - Integration tests:
    - Successful run (build and run).
    - Failed build.
    - Failed run.
  - Ensure events and summary match expectations.

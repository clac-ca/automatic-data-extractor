> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` -> `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

Architecture & spec

- [ ] Finalize & commit event catalog and migration table (`020-EVENT-TYPES-REFERENCE.md`).
- [ ] Finalize HTTP API design for runs/builds & streaming (`030-API-DESIGN-RUNS-AND-BUILDS.md`).
- [ ] Finalize build streaming & integration notes (`080-BUILD-STREAMING.md`).
- [ ] Finalize console logging + subprocess streaming spec (`090-CONSOLE-LOGGING.md`).

Implementation

- [ ] Implement canonical `AdeEvent` envelope, `console.line`, and new payload models in ade-api + ade-engine.
- [ ] Implement central event dispatcher in ade-api (ID/sequence assignment, NDJSON sink, SSE fan-out).
- [ ] Replace existing v1 run & build routes with new behavior (no `/v2`; new semantics are the default).
- [ ] Integrate build + run orchestration with new events, including subprocess console streaming.
- [ ] Implement `RunSummaryBuilder` and canonical `run.completed`, updating DB and UI.
- [ ] Update ade-web to consume unified run event stream and render build + run logs consistently.
- [ ] Remove all v1 event types, streaming codepaths, and docs (ensure no stale references remain).

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Implement central event dispatcher - merged in #1234`

---

## 1. Scope & non-goals

**Scope**

- Replace the existing ADE streaming and event system with a **single, unified, event-driven run stream**:
  - One **run ID** owns the sequence.
  - Build and run events are in **one ordered stream**.
  - Frontend and tooling consume the **same events**.

**Non-goals**

- No backward compatibility with v1 streaming:
  - We **do not** keep old event shapes (`build.console`, `run.console`, etc.).
  - We **do not** add `/v2` endpoints. New semantics replace the old ones in-place.
  - We **do not** maintain NDJSON streaming as a primary protocol; we standardize on **SSE for live streaming**, NDJSON for storage and offline retrieval.

---

## 2. Files in this work package

- `020-EVENT-TYPES-REFERENCE.md`
  - Canonical event envelope.
  - Final list of event types and payloads.
  - Table of **current (v1)** vs **new (final)** events, including what is removed, renamed, or added.

- `030-API-DESIGN-RUNS-AND-BUILDS.md`
  - HTTP endpoints for creating runs, streaming events, and reading summaries.
  - How builds integrate into the run stream.
  - Query params (`stream`, `from_sequence`, etc.) and media types.

- `040-IMPLEMENTATION-PLAN.md`
  - Concrete, phased plan to implement the new system.
  - Where to add code in ade-api and ade-engine.
  - When/how to remove v1 code.

- `080-BUILD-STREAMING.md`
  - Current build streaming behavior (v1).
  - Target design: build logs and events integrated into the **run's** event stream.
  - How the dedicated build endpoint behaves after the refactor.

- `090-CONSOLE-LOGGING.md`
  - Unified `console.line` event type.
  - How ade-api captures stdout/stderr from subprocesses and turns them into events.
  - How engine-emitted structured events (JSON) are handled vs raw console prints.

---

## 3. High-level design decisions (summary)

- **One canonical event envelope** (`AdeEvent`) with:
  - `type`, `event_id`, `created_at`, `sequence`, `source`,
  - `workspace_id`, `configuration_id`, `run_id`, `build_id?`,
  - `payload`.

- **Single log event type**: `console.line`
  - Replaces `build.console`, `run.console`, and engine's `run.console`.
  - Same shape everywhere; `scope` distinguishes build vs run.

- **Unified lifecycle events**:
  - `build.created`, `build.started`, `build.phase.started`, `build.phase.completed`, `build.completed`.
  - `run.queued`, `run.started`, `run.phase.started`, `run.phase.completed`, `run.completed`.
  - `run.table.summary`, `run.validation.summary`, optional `run.validation.issue`.
  - `run.error` for structured error context.

- **API streaming pattern** (inspired by OpenAI /responses):
  - `POST /workspaces/{workspace_id}/configurations/{configuration_id}/runs?stream=true`
    - Starts the run **and** streams events as SSE (`text/event-stream`).
  - `GET /.../runs/{run_id}/events?stream=true&from_sequence=...`
    - Attach to an existing run's stream; replay from `sequence`.

- **Storage format**:
  - Event logs persisted as **NDJSON** per run:
    - `events.ndjson` (one JSON object per line).

All details live in the sub-docs. This file is just your map.

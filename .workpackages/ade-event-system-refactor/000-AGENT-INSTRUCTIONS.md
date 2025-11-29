# ADE Events & Runs – Work Package

> **Agent instruction (read first):**
>
> - Treat this work package as the **single source of truth** for the new ADE run + event system.
> - This design **replaces the old v1 endpoints and event formats**. We have no external users; you are free to delete v1 code and migration shims.
> - There is **no `/v2` API**. The endpoints defined here (`/runs`, `/runs/{run_id}`, `/runs/{run_id}/events`, etc.) are the canonical interface going forward.
> - Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> - Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> - Prefer small, incremental commits aligned to checklist items.
> - If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

- [ ] Finalize and implement the **canonical event envelope** and event payload models in shared ADE code (ade-api + ade-engine).
- [ ] Implement the **event dispatcher** in ade-api (ID/sequence allocation, NDJSON persistence, SSE fan-out).
- [ ] Implement the new **HTTP API surface**:
  - [ ] `POST /runs` (create run job).
  - [ ] `GET /runs/{run_id}` (status + summary).
  - [ ] `GET /runs/{run_id}/events` (JSON/NDJSON history).
  - [ ] `GET /runs/{run_id}/events` with `Accept: text/event-stream` (live SSE).
  - [ ] Optional: `POST /runs?stream=true` convenience endpoint (create + stream).
- [ ] Refactor ade-api **run/build orchestration** to emit the new lifecycle events (`run.queued`, `build.*`, `run.phase.*`, `console.line`, etc.) via the dispatcher.
- [ ] Implement `RunSummaryBuilder` in ade-api and wire it into run finalization to emit canonical `run.completed` and persist the summary to the `runs` table.
- [ ] Update ade-engine to emit **structured internal events** (build phases, run phases, `console.line`, `run.table.summary`, optional `run.validation.summary`, `run.error`) in the new payload shapes.
- [ ] Wire ade-engine’s **event output** into ade-api’s dispatcher (parse engine events, wrap with envelope, assign `event_id`/`sequence`).
- [ ] Update ade-web **config builder UI** to use the new `/runs` + `/runs/{run_id}/events` streaming API and render build/run logs, phases, and table summaries.
- [ ] Remove **all v1 endpoints and event formats** from ade-api, ade-engine, ade-web, and shared libraries; update any references in docs and CLI tooling.
- [ ] Add tests, metrics, and operational safeguards (backpressure, error handling, multi-instance behavior) for the new event system.

> **Agent note:**  
> Add or remove checklist items as needed. Keep brief status notes inline, for example:  
> `- [x] Implement event dispatcher in ade-api — merged in #1234`

---

## File Map

Use these files together:

- `010-HIGH-LEVEL-DESIGN.md` – overall goals, mental model, and architecture.
- `020-API-SPEC.md` – external HTTP API surface for runs and events.
- `030-EVENT-MODEL.md` – canonical event envelope and event type catalog.
- `040-RUN-SUMMARY.md` – run summary model and summary builder logic.
- `050-ADE-API-IMPLEMENTATION.md` – ade-api implementation plan (dispatcher, SSE, NDJSON, orchestration).
- `060-ADE-ENGINE-IMPLEMENTATION.md` – ade-engine implementation plan (event emission, phases, table summaries).
- `070-MIGRATION-AND-CLEANUP.md` – removal of v1 code, rollout, and cleanup.

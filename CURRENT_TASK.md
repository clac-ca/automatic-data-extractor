# 🚧 ADE Backend Rewrite – Next Focus

## Status Snapshot
- Document storage adapter implemented with safe path resolution and streaming I/O helpers.
- `/documents` endpoints rebuilt to support upload/list/detail/download/delete flows with audit events.
- Unit/integration coverage exercises document happy paths plus oversize upload and missing-file scenarios.

## Goal for This Iteration
Deliver the first working slice of the new jobs workflow: accept job submissions, resolve document/configuration inputs, run the stub extractor synchronously, and expose list/detail endpoints that surface job status and metrics.

## Scope
1. **Jobs domain foundations**
   - Implement a synchronous `JobsService` that validates inputs, persists `jobs` rows, and orchestrates the in-process extractor stub while emitting status events.
   - Reintroduce a `jobs` router with list/detail/submit endpoints aligned with `fastapi-best-practices.md` patterns (class-based views, explicit dependencies, permission guards).
   - Capture status transitions (`pending` → `running` → `succeeded`/`failed`) on the existing schema, storing basic metrics/log summaries for responses.
2. **Extractor hook-up**
   - Restore the lightweight processor stub under `backend/processor/` (no heavy logic yet) and invoke it from the service using `run_in_threadpool` for blocking work.
   - Ensure extractor failures propagate cleanly with job status `failed` and reason recorded for API responses/tests.
3. **Tests & fixtures**
   - Add integration tests covering successful job submission, invalid document/configuration references, and extractor failure paths.
   - Provide unit coverage around the service to exercise status transitions and event emission where practical.
4. **Documentation & follow-ups**
   - Update `docs/backend_rewrite.md` with the new jobs architecture sketch and any deviations discovered during implementation.
   - Outline remaining tasks (results module refresh, retention policies) for the subsequent iteration.

## Definition of Done
- `/jobs` endpoints operate end-to-end against the rewritten service and stub extractor without relying on the old worker queue.
- Job records reflect status transitions with persisted metrics/log excerpts.
- Tests cover happy paths and the primary error scenarios (invalid inputs, extractor failure).
- Repository continues to align with `fastapi-best-practices.md` (thin routers, services owning business logic, blocking work offloaded).

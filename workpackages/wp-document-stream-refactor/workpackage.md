# Work Package: Document Stream Refactor Rollup

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Break the document stream refactor into focused workstreams (DB change feed, backend realtime API, frontend integration, and ops/testing). Align with the research pattern: push a lightweight notification, pull deltas and rows.

### Research References (read first)

- `workpackages/wp-document-stream-refactor/research.md` lines 35-165 (context, constraints, target architecture)
- `workpackages/wp-document-stream-refactor/research.md` lines 168-292 (API design, event model, token semantics)
- `workpackages/wp-document-stream-refactor/research.md` lines 295-465 (DB options + emit strategy)
- `workpackages/wp-document-stream-refactor/research.md` lines 469-988 (backend, frontend, UX, performance, testing, observability)

### Scope

- In: change feed design, realtime notify stream, delta + list id filter support, frontend reconciliation, observability/testing.
- Out: full realtime totals/facets, WebSocket replacement, redesign of the documents list API.

### Plan of Action (recommended order)

1) DB change feed (schema + triggers + retention)  
2) Backend realtime API (stream route + delta + id filter)  
3) Frontend integration (SSE + delta + list(id) membership + UX rules)  
4) Docs and tests (update docs/types, add unit/integration tests)  
5) Ops/observability (metrics/logs, retention runbook)

### Work Breakdown Structure (WBS)

0.1 Research review
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 35-292 (context, constraints, API, event model)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 295-465 (DB design + emit strategy + DDL examples)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 469-988 (backend, frontend, UX, performance, testing, observability + code examples)
1.0 Architecture decisions
  1.1 Change feed decision
    - [ ] Decide between append-only partitioned log vs coalesced state table (Research: lines 295-426)
    - [ ] Decide retention window and maintenance mechanism (Research: lines 347-381)
  1.2 Realtime contract
    - [ ] Confirm push-notify plus pull-delta semantics (token/seq driven) (Research: lines 89-129, 168-221, 254-292)
    - [ ] Confirm event ops (upsert/delete) and list(id filter) membership strategy (Research: lines 254-265, 223-239)
    - [ ] Lock stream route to `/documents/stream` (Design decision)
    - [ ] Lock stream payload to `{documentId, op, token}` and remove row payloads (Design decision)
    - [ ] Lock change emission to DB-level triggers (Design decision)
2.0 DB change feed implementation (subpackage)
  2.1 DB change feed workpackage
    - [ ] Complete `workpackages/wp-document-stream-refactor/subpackages/db-change-feed/workpackage.md`
3.0 Backend realtime API (subpackage)
  3.1 Backend API workpackage
    - [ ] Complete `workpackages/wp-document-stream-refactor/subpackages/backend-realtime-api/workpackage.md`
4.0 Frontend realtime integration (subpackage)
  4.1 Frontend integration workpackage
    - [ ] Complete `workpackages/wp-document-stream-refactor/subpackages/frontend-documents-realtime/workpackage.md`
5.0 Ops, observability, and testing (subpackage)
  5.1 Ops/testing workpackage
    - [ ] Complete `workpackages/wp-document-stream-refactor/subpackages/ops-observability-testing/workpackage.md`
6.0 Documentation and tests (subpackage)
  6.1 Docs/tests workpackage
    - [ ] Complete `workpackages/wp-document-stream-refactor/subpackages/docs-and-tests/workpackage.md`

### Open Questions

- Which change feed model should we adopt (append-only log vs coalesced state)? (Research: lines 295-426)
- What retention window and maintenance approach do we want (app cron vs pg_cron)? (Research: lines 347-367)
- Should the SSE stream use only workspace scope, or add user-scoped filtering? (Research: lines 123-129, 187-197)

---

## Acceptance Criteria

- Subpackages are defined and scoped with concrete, verifiable tasks. (Research: lines 960-978)
- Decisions about change feed model and retention are recorded and reflected in subpackages. (Research: lines 295-381)
- The rollup WBS is aligned with the research doc and current repo constraints. (Research: lines 14-31, 35-165)

---

## Definition of Done

- All subpackage workpackages exist under `workpackages/wp-document-stream-refactor/subpackages/`. (Research: lines 960-978)
- The rollup WBS references those subpackages and captures open decisions. (Research: lines 14-31, 35-165)

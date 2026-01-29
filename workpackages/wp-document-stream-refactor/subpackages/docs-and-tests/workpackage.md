# Work Package: Documentation and Tests

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Update API/UI documentation and add tests that validate the delta + list(id filter) flow, including resync behavior. Keep docs aligned with the final route `/documents/stream` and the minimal stream payload.

### Research References (read first)

- `workpackages/wp-document-stream-refactor/research.md` lines 168-239 (API design: stream, delta, list id filter)
- `workpackages/wp-document-stream-refactor/research.md` lines 903-921 (testing plan)
- `workpackages/wp-document-stream-refactor/research.md` lines 951-978 (implementation checklist)

### Scope

- In: API docs, frontend docs, OpenAPI types, backend unit/integration tests for delta + list(id) flow.
- Out: load testing harness, production monitoring dashboards.

### Work Breakdown Structure (WBS)

0.1 Research review
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 168-239 (API design details)
  - [x] Read `workpackages/wp-document-stream-refactor/research.md` lines 903-921 (testing plan)
1.0 Documentation updates
  1.1 API docs
    - [x] Update docs to `/documents/stream` and `/documents/delta` routes (Research: lines 168-221)
    - [x] Document list(id filter) membership flow (Research: lines 223-250)
    - [x] Remove lookup endpoint references and `include=rows` from stream docs (Design decision)
    - [x] Document minimal stream payload `{documentId, op, token}` (Design decision)
    - [x] Document partitioned retention strategy (daily partitions + drop old partitions) (Design decision)
  1.2 OpenAPI/types
    - [x] Regenerate OpenAPI + frontend types after route, payload, and filter changes (Research: lines 168-239)
2.0 Tests
  2.1 Backend unit tests
    - [x] Token encode/decode roundtrip (Research: lines 905-912)
    - [x] Delta ordering + 410 resync behavior (Research: lines 907-913)
    - [x] List id filter membership query (Research: lines 223-239)
 2.2 Integration tests
    - [ ] SSE notify -> delta -> list(id filter) flow (Research: lines 918-921)

### Open Questions

- None. API docs updated in `docs/reference/api-guide.md`; frontend tests deferred.

---

## Acceptance Criteria

- Docs reflect `/documents/stream`, `/documents/delta`, list(id filter) membership flow, and minimal stream payload. (Research: lines 168-239)
- OpenAPI/types are regenerated and consistent with docs. (Research: lines 168-239)
- Tests cover token, delta ordering/410, and list(id filter) membership logic. (Research: lines 903-921)

---

## Definition of Done

- Documentation updated and reviewed. (Research: lines 168-239)
- Tests added for delta + list(id filter) flow. (Research: lines 903-921)

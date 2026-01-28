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
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 168-239 (API design details)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 903-921 (testing plan)
1.0 Documentation updates
  1.1 API docs
    - [ ] Update docs to `/documents/stream` and `/documents/delta` routes (Research: lines 168-221)
    - [ ] Document list(id filter) membership flow (Research: lines 223-250)
    - [ ] Remove lookup endpoint references and `include=rows` from stream docs (Design decision)
    - [ ] Document minimal stream payload `{documentId, op, token}` (Design decision)
    - [ ] Document partitioned retention strategy (daily partitions + drop old partitions) (Design decision)
  1.2 OpenAPI/types
    - [ ] Regenerate OpenAPI + frontend types after route, payload, and filter changes (Research: lines 168-239)
2.0 Tests
  2.1 Backend unit tests
    - [ ] Token encode/decode roundtrip (Research: lines 905-912)
    - [ ] Delta ordering + 410 resync behavior (Research: lines 907-913)
    - [ ] List id filter membership query (Research: lines 223-239)
  2.2 Integration tests
    - [ ] SSE notify -> delta -> list(id filter) flow (Research: lines 918-921)

### Open Questions

- Where should API docs live (ade-web docs vs ade-api docs)?
- Do we add frontend integration tests now or later?

---

## Acceptance Criteria

- Docs reflect `/documents/stream`, `/documents/delta`, list(id filter) membership flow, and minimal stream payload. (Research: lines 168-239)
- OpenAPI/types are regenerated and consistent with docs. (Research: lines 168-239)
- Tests cover token, delta ordering/410, and list(id filter) membership logic. (Research: lines 903-921)

---

## Definition of Done

- Documentation updated and reviewed. (Research: lines 168-239)
- Tests added for delta + list(id filter) flow. (Research: lines 903-921)

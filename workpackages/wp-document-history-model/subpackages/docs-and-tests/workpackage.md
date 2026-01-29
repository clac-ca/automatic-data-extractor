# Work Package: Docs and Tests

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - WBS checkboxes are for implementation execution; do not mark complete during planning.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Update documentation and tests to reflect the simplified, most common data model and API contracts. Remove references to idempotency keys, ETags, and document version fields where applicable.

### Scope

- In:
  - API docs update for document list, update, delete, and stream endpoints.
  - Developer docs describing terminology and data model decisions.
  - Test plan updates for removed ETag and idempotency behavior.
  - Documentation note: DB tables remain files/file_versions; API/UI uses documents terminology.
  - Document standard kind values (input/output/log/export).
- Out:
  - Implementation of code changes (handled in follow-on execution).

### Work Breakdown Structure (WBS)

1.0 Documentation updates
  1.1 API docs
    - [ ] Remove If-Match/ETag references from document endpoints.
    - [ ] Remove Idempotency-Key references from uploads/runs/API keys.
    - [ ] Update document stream + delta docs for numeric cursor contract.
  1.2 Architecture docs
    - [ ] Add/refresh terminology section describing document_versions vs audit_log vs change feed.
    - [ ] Document the chosen common structure and rationale.
2.0 Tests + fixtures
  2.1 Backend tests
    - [ ] Remove/update tests that assert ETag/If-Match or idempotency behavior.
    - [ ] Update fixtures that rely on removed columns (doc_no, expires_at, version).
  2.2 Realtime tests
    - [ ] Ensure SSE -> delta -> list(id filter) integration test matches the numeric cursor contract.
  2.3 Frontend tests/types
    - [ ] Update frontend API tests for removed headers and fields.
    - [ ] Regenerate OpenAPI-driven types if needed.

### Open Questions

- Resolved: Update public API docs and developer docs (internal runbooks optional).
- Resolved: Remove optimistic concurrency/idempotency tests; keep stream/delta tests.

### Outputs

#### Documentation checklist

- API docs reflect removal of ETag/If-Match and Idempotency-Key.
- Document stream/delta endpoints match numeric cursor contract.
- Docs explain that DB tables remain `files`/`file_versions`, while API/UI uses "documents".
- Docs list standard `kind` values: `input`, `output`, `log`, `export`.

#### Tests impact summary

- Remove tests for optimistic concurrency and idempotent upload behavior.
- Update fixtures that rely on `files.version` or `expires_at`.
- Keep SSE -> delta -> list(id filter) integration coverage.

---

## Acceptance Criteria

- Docs reflect the new simplified contract and terminology.
- Tests plan includes removal of old behaviors and confirmation of new stream behavior.

---

## Definition of Done

- Documentation and test updates are fully specified and aligned with the model decisions.

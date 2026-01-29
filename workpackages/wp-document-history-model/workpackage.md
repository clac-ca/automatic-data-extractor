# Work Package: Document History Model and Change Feed Standardization

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - WBS checkboxes are for implementation execution; do not mark complete during planning.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Define the most common terminology and data model for document metadata history, byte history, and realtime change feeds, then translate those decisions into a concrete schema and API contract. Use separate subpackages for terminology/architecture, schema/migrations, API/stream contracts, and docs/tests to keep the workstreams clear.

### Scope

- In:
  - Glossary and terminology alignment (document, document version, audit log, change feed, outbox, cursor).
  - Decision matrix for audit_log vs document_changes and unified vs split history models.
  - Target schema and migration plan for the chosen common structure.
  - API/stream contract updates aligned with simplified model.
  - Docs and tests plan to match the new model.
  - Standardize file kind values, name_key behavior, and storage metadata expectations.
- Out:
  - Implementation work beyond the plan and workpackages (handled in follow-on execution).
  - Any changes to ade-engine or ade-config (out of scope).

### Work Breakdown Structure (WBS)

1.0 Terminology and architecture alignment (implementation)
  1.1 Apply terminology alignment
    - [ ] Update docs to use the standard document/document_version/change-feed terms.
    - [ ] Ensure API/UI naming stays on "documents" while DB stays files/file_versions.
2.0 Data model and migrations
  2.1 Schema + migration execution
    - [ ] Add an Alembic migration for schema changes (drops/renames/backfills).
    - [ ] Update ORM models to match the new schema.
    - [ ] Update ade-worker schema/helpers to match the new schema.
3.0 API and stream contracts
  3.1 API surface changes
    - [ ] Remove ETag/If-Match handling from document endpoints.
    - [ ] Remove Idempotency-Key handling from uploads/runs/API keys.
    - [ ] Update document list/detail payloads to remove version/docNo/expiresAt/etag.
  3.2 Change feed alignment
    - [ ] Ensure SSE + delta payloads stay aligned with numeric cursor contract.
4.0 Docs and tests
  4.1 Docs/types/tests updates
    - [ ] Update API/docs references for removed headers/fields.
    - [ ] Update backend/worker/frontend tests impacted by the schema and API changes.
    - [ ] Regenerate OpenAPI + frontend API types if needed.

### Open Questions

- Resolved: Use `document_changes` for realtime deltas; add audit_log only if compliance/history is required.
- Resolved: Keep documents + document_versions (byte history) without a unified revision table.
- Resolved: Drop `idempotency_keys` and `documents.version` for maximum simplicity (no backward compatibility).

---

## Acceptance Criteria

- A glossary defines standard terminology and the meaning of audit_log, document_versions, and change feed tables.
- The target data model is documented with rationale and trade-offs.
- A migration plan exists for the chosen model, including any table/column removals.
- API and stream contracts are documented to match the chosen model and simplifications.
- Docs/tests scope is captured with concrete tasks.

---

## Definition of Done

- All subpackage workpackages are written, internally consistent, and aligned to the chosen common structure.
- Open questions are either resolved or explicitly left as decisions for the next execution phase.

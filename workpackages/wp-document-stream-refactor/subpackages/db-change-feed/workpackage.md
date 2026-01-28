# Work Package: Document Change Feed (DB)

> Agent instruction:
>
> - Treat this work package as the single source of truth.
> - Keep the WBS checklist up to date: change [ ] -> [x] as tasks complete.
> - If you must change the plan, update this document first, then the code.

---

## Plan

Implement a durable document change feed in Postgres (schema, sequence, and emit path) so realtime notifications can be replayed and used for delta queries. Choose the change feed model up front and wire change emission via **DB-level triggers** from document and run mutations.

### Partitioning and Retention (explicit)

For the append-only option, use **daily range partitions** on `changed_at` and drop old partitions for retention. Avoid `DELETE`-based cleanup to prevent vacuum bloat.

### Research References (read first)

- `workpackages/wp-document-stream-refactor/research.md` lines 295-426 (DB design options A/B and schemas)
- `workpackages/wp-document-stream-refactor/research.md` lines 430-465 (event emission sources + NOTIFY payload constraints)
- `workpackages/wp-document-stream-refactor/research.md` lines 859-863 (partition retention guidance)
- `workpackages/wp-document-stream-refactor/research.md` lines 953-959 (DB implementation checklist)

### Scope

- In: schema/migration, sequence/token strategy, emit helper or trigger, retention mechanism.
- Out: SSE endpoint, delta/list API changes, frontend UI changes.

### Work Breakdown Structure (WBS)

0.1 Research review
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 295-418 (DB options + DDL examples)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 420-465 (emit strategy + NOTIFY limits)
  - [ ] Read `workpackages/wp-document-stream-refactor/research.md` lines 859-863 (partition retention guidance)
1.0 Change feed design
  1.1 Choose model
    - [ ] Decide append-only partitioned log vs coalesced state table (Research: lines 295-426; code example lines 313-337, 400-418)
    - [ ] Confirm token shape (ts + seq) and serialization format (Research: lines 274-292)
  1.2 Event semantics
    - [ ] Confirm ops are `upsert` and `delete` (Research: lines 256-262)
    - [ ] Keep NOTIFY payload minimal (workspace_id + token/seq) (Research: lines 459-465, 845-857)
2.0 Schema + migration
  2.1 Migration DDL
    - [ ] Add change feed table and indexes (Research: lines 313-337; code example lines 313-337)
    - [ ] Add sequence (if using coalesced state) (Research: lines 400-424; code example lines 400-418)
    - [ ] Add retention structure (partitions or cleanup routine) (Research: lines 339-381)
3.0 Emit path
  3.1 Emit helper
    - [ ] Add DB function to emit change rows + NOTIFY (trigger target) (Research: lines 447-458)
    - [ ] Add pg_notify payload (workspace_id + token/seq) (Research: lines 459-465)
  3.2 Wire emit points
    - [ ] Add AFTER triggers on `files` for insert/update/delete (Design decision)
    - [ ] Add AFTER triggers on `file_tags` for insert/delete (Design decision)
    - [ ] Add AFTER triggers on `runs` for insert/update (Design decision)
    - [ ] `files` trigger: emit `delete` when `deleted_at` transitions null -> not null; otherwise `upsert` (Design decision)
    - [ ] `runs` trigger: emit only on status/start/completion/output/error changes (Design decision)
    - [ ] Map `runs.input_file_version_id` -> `file_versions.file_id` to resolve document_id (Design decision)
    - [ ] Identify document mutations that impact list rows (files, tags, runs) (Research: lines 432-441)
    - [ ] Emit on document changes and run updates that affect list state (Research: lines 447-455)
    - [ ] Avoid event storms from wide tables (run_fields/run_table_columns) (Research: lines 442-445)
4.0 Retention and validation
  4.1 Retention policy
    - [ ] Implement partition creation/drop or cleanup job (Research: lines 347-367)
  4.2 Basic verification
    - [ ] Validate changes are written and ordered per workspace (Research: lines 266-272)

### Open Questions

- Which model is final (append-only vs coalesced state)? (Research: lines 295-426)
- What retention window do we want (7 days, 14 days, other)? (Research: lines 352-353)
- Do we store any payload fields beyond ids/op for debugging? (Research: lines 323-327)

---

## Acceptance Criteria

- Change feed table and sequence (if required) exist with required indexes. (Research: lines 313-337, 400-418)
- Change emission is wired from document and run mutations. (Research: lines 430-458)
- NOTIFY payloads include workspace_id and token/seq and are under payload limits. (Research: lines 459-465, 845-857)
- Retention mechanism is defined and documented. (Research: lines 347-367, 859-863)

---

## Definition of Done

- Migration(s) added and applied cleanly. (Research: lines 313-337, 400-418)
- Change feed rows are recorded and queryable for delta. (Research: lines 201-215, 266-272)
- A retention plan exists (partition drop or cleanup) and is executable. (Research: lines 347-367, 859-863)

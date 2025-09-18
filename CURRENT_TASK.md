# Current Task — Unified audit log foundation

## Goal
Stand up a lightweight, extensible audit log that records key lifecycle events
across ADE, starting with document deletions, so operators get a durable,
actionable history without complicating the rest of the system.

## Background
- Today we mutate `deleted_at`/`deleted_by` on the `documents` row itself. Once a
  second purge or manual delete occurs, that context disappears.
- Other actions (document uploads, configuration changes, job executions) will
  also need immutable trails as ADE grows. Building a single audit substrate now
  avoids bespoke tables for each workflow.
- Operations values determinism and debuggability over throughput. A simple SQL
  table that all services can write to keeps the design transparent and easy to
  extend.
- Legal/litigation hold remains out of scope; we just need consistent auditing of
  the events ADE already performs.

## Scope
- Design an `audit_events` table + SQLAlchemy model keyed by ULID with:
  - `event_type` (e.g., `document.deleted`, `document.uploaded` in future).
  - `entity_type` + `entity_id` strings so the log can reference any model.
  - `occurred_at` timestamp defaulting to `datetime.utcnow()`.
  - `actor_type`/`actor_id` and optional display metadata (`actor_label`).
  - `source` (API, scheduler, CLI) and optional `request_id` for tracing.
  - `payload` JSON column for structured per-event details (e.g., bytes reclaimed,
    delete reason, missing on disk flag).
- Add a small `audit_log` service helper that exposes `record_event(...)` and
  centralises validation (required fields, JSON serialisation, enum mapping).
- Update document deletion flows to emit a `document.deleted` event when a row
  transitions from active to deleted (manual API, CLI purge, background purge),
  ensuring retries remain idempotent by checking the soft-delete state before
  logging.
- Provide FastAPI read endpoints:
  - `GET /audit-events` with filters for `entity_type`, `entity_id`, `event_type`,
    time range, and source.
  - `GET /documents/{document_id}/audit-events` as a convenience wrapper that
    applies the above filters.
- Expand Pydantic schemas/OpenAPI docs for the new endpoints, making the payload
  field explicit so future events can document their structure.
- Cover the happy paths with pytest: recording manual/automatic deletion events,
  idempotency on repeated calls, payload serialisation, and list filtering.
- Document the audit log in the README, glossary, and retention guide, clarifying
  how to query it for deletions and how other teams should add new event types.

## Out of scope
- Building UI visualisations or dashboards for the log.
- Streaming/queue-based audit delivery; all writes go straight to SQLite.
- Emitting events for every possible action right now—focus on deletions, but
  note how to extend to uploads/config changes later.
- Litigation hold workflows or retention overrides.

## Deliverables
1. `audit_events` table + SQLAlchemy model/migration with indexes on
   `(entity_type, entity_id)` and `event_type`.
2. Shared audit log service helper with unit tests validating payload handling
   and enums.
3. Document deletion pathways updated to call the helper and emit consistent
   events without duplicates.
4. FastAPI endpoints + schemas that surface audit events with filtering support
   and tests covering manual vs. automated deletions.
5. Documentation updates describing the audit log design, usage, and extension
   points for new event types.

## Definition of done
- Deleting a document through any existing pathway logs a `document.deleted`
  audit event accessible through the new endpoints; repeated deletes do not
  create duplicates.
- Operators can query deletion history via API filters to see when, how, and by
  whom a document was removed, including metadata like bytes reclaimed.
- Other teams understand how to register new event types against the shared
  audit log without schema changes beyond payload evolution.
- Documentation reiterates that litigation hold is out of scope and points to the
  audit endpoints for operational review.

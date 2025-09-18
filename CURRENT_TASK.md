# Current Task — Ship a simple, reusable audit log

## Goal
Design and implement a lightweight audit logging pipeline that ADE can
reuse for any user- or system-driven action, starting with document
deletions. The mechanism should be simple to reason about today while
remaining flexible enough for future event types.

## Why this matters
- Today deletions only toggle `deleted_at`/`deleted_by` on the `documents`
  record. Once the row disappears, so does the trail.
- Other workflows (uploads, config edits, job executions) will need immutable
  history soon. Standing up one shared pipeline now keeps future work cheap.
- Operations wants determinism and clarity over throughput. A single SQL table
  with a thin helper service stays transparent and easy to reason about.
- Litigation hold remains out of scope; we are just capturing the actions ADE
  already performs.

## Guiding principles
1. **Keep it boring** – SQLite table + SQLAlchemy ORM + service helper. No
   queues or cross-service plumbing.
2. **Model any entity** – Store generic `entity_type`/`entity_id` pairs so every
   feature can log without schema changes.
3. **Capture the actor + context** – Include optional actor metadata and a JSON
   payload for structured details (e.g., deletion reason, bytes reclaimed).
4. **Make reads easy** – Provide filtered list endpoints instead of bespoke
   queries in every caller.
5. **Document the pattern** – Show other teams how to emit their own events.
6. **Stay additive** – Recording an event must never mutate or block the
   original workflow; failures surface but should not roll back primary actions
   unless explicitly opted-in.

## Solution overview
Break the work into three pieces that callers can reuse independently:

1. **Data model** – `audit_events` table keyed by ULID with:
   - `event_type` (string: `document.deleted`, `document.uploaded`, etc.).
   - `entity_type`, `entity_id` (strings) for cross-model coverage.
   - `occurred_at` UTC timestamp defaulting to `datetime.utcnow()`.
   - Optional actor columns: `actor_type`, `actor_id`, `actor_label`.
   - Optional origin info: `source` (API, scheduler, CLI) + `request_id`.
   - `payload` JSON column for event-specific context; ensure deterministic
     serialisation.
   - Indexes on `(entity_type, entity_id)` and `event_type` for filtered reads.

2. **Service + schema layer** – `services/audit_log.py` exposes a single
   `record_event(...)` helper that:
   - Accepts strongly typed inputs (Pydantic model or dataclass) and normalises
     them before persistence.
   - Handles ULID generation, timestamp defaulting, validation, and JSON
     serialisation so callers remain simple.
   - Provides read helpers (`list_events`, `list_entity_events`) with optional
     filters (entity tuple, event type, source, request ID, time range).
   - Logs internal failures and lets the caller decide whether to treat them as
     fatal.

3. **HTTP surface** – FastAPI routes under `/audit-events` that
   - Return paginated audit events with filter query parameters mirroring the
     service helpers.
   - Provide `GET /documents/{document_id}/audit-events` to scope events to a
     specific document without repeating filter wiring.

## Document deletion integration
- Update the document deletion service to call `record_event(...)` after a
  successful soft-delete, using `event_type="document.deleted"` and including
  the user context and soft-delete metadata in the payload.
- Guard against duplicate logging by checking whether the document was already
  marked deleted before emitting an event (idempotency).
- Capture scheduled purges as the same event type with a different `source`
  (e.g., `scheduler`).

## Testing + validation
- Unit tests around the service helper ensure ULID uniqueness, JSON payload
  preservation, optional metadata handling, and idempotent retries.
- API tests cover filtering, pagination, and document-specific views.
- Integration test exercises the deletion flow to confirm the event is stored
  exactly once and is retrievable via both API routes.

## Documentation updates
- README, glossary, and the retention guide describe the audit log, the common
  event format, and how teams emit their own events.
- Provide an example payload for `document.deleted` to set expectations for
  future event authors.

## Definition of done
- Every deletion path emits a single `document.deleted` audit event accessible
  via the new endpoints; retries do not double-log.
- Operators can filter audit events to inspect document deletion history with
  actor/context metadata.
- Other teams know how to call `record_event(...)` for their own workflows
  without schema edits beyond payload evolution.
- Documentation reiterates that litigation hold is out of scope and highlights
  the audit endpoints for operational review.

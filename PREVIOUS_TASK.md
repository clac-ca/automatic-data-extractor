# Previous Task — Ship a simple, reusable audit log

## Goal
Stand up a straightforward audit log that any ADE workflow can write to, while
keeping the implementation intentionally boring. Document deletions are the
first concrete event we will record; the same mechanism should let future
features append their own events without schema changes or deep plumbing.

## Why this matters
- Deleting a document today only flips `deleted_at`/`deleted_by` on the row, so
  the history disappears once the record is cleaned up.
- Uploads, configuration edits, and job executions will need immutable history
  soon; one shared audit log keeps future work cheap and consistent.
- Operations prioritises determinism over throughput. A single SQL table with a
  thin helper service keeps the trail transparent and debuggable.
- Litigation hold remains out of scope—we simply capture the actions ADE
  already performs in a durable event feed.

## Design guardrails
1. **Keep it boring** – SQLite table + SQLAlchemy ORM + helper service. No
   queues, brokers, or cross-service dependencies.
2. **Model any entity** – Store `entity_type`/`entity_id` pairs so every feature
   can log without schema tweaks.
3. **Record the actor + context** – Optional actor metadata and a JSON payload
   capture who did the thing and any structured details (reason, bytes, etc.).
4. **Readable by default** – Provide simple query helpers/endpoints instead of
   bespoke SQL sprinkled across callers.
5. **Non-blocking** – Logging is additive. If writing an event fails we surface
   it, but the main workflow keeps its own error handling.

## Planned implementation
Split the work into layers we can reason about independently and reuse later:

1. **Data model** – Add an `audit_events` table keyed by ULID with:
   - `event_type` (e.g., `document.deleted`).
   - `entity_type`/`entity_id` (strings) for cross-model coverage.
   - `occurred_at` UTC timestamp defaulting to `datetime.utcnow()`.
   - Optional actor columns: `actor_type`, `actor_id`, `actor_label`.
   - Optional origin info: `source` (API, scheduler, CLI) and `request_id`.
   - `payload` JSON column for structured context (ensure deterministic
     serialisation order).
   - Indexes on `(entity_type, entity_id)` and `event_type` to keep lookups
     cheap.

2. **Audit service** – Add `services/audit_log.py` exposing:
   - `record_event(...)` that accepts a typed input model, handles ULID
     generation, timestamps, validation, and JSON serialisation, and returns the
     stored ORM row.
   - `list_events(...)`/`list_entity_events(...)` helpers with optional filters
     (entity tuple, event type, source, request ID, time range) to centralise
     query logic.
   - Error handling that logs failures and lets the caller decide whether to
     treat them as fatal.

3. **API surface** – FastAPI routes under `/audit-events` that:
   - Return paginated events with filters mirroring the service helpers.
   - Provide `GET /documents/{document_id}/audit-events` as a convenience
     wrapper so document-focused tooling can avoid custom filters.

## Document deletion integration
- Update the document deletion service to call `record_event(...)` after a
  successful soft-delete, using `event_type="document.deleted"` and including
  user context plus soft-delete metadata in the payload.
- Prevent duplicate logging by short-circuiting if the document was already
  marked deleted when we entered the workflow (idempotency guard).
- When scheduled purges run, emit the same `document.deleted` event type with a
  different `source` (e.g., `scheduler`).

## Testing + validation
- Unit tests around the audit service cover ULID uniqueness, JSON payload
  preservation, optional metadata handling, and idempotent retries.
- API tests cover filtering, pagination, and document-specific views.
- Integration test for the deletion flow confirms exactly one audit event is
  persisted and retrievable via both API routes.

## Documentation updates
- README, glossary, and the retention guide describe the audit log, shared
  event format, and how teams call `record_event(...)`.
- Include an example `document.deleted` payload so future event authors know
  what “good” looks like.

## Definition of done
- Every deletion path emits a single `document.deleted` event that is accessible
  via the new endpoints; retries do not double-log.
- Operators can filter audit events to review deletion history with actor and
  context metadata.
- Other teams can adopt `record_event(...)` for their workflows without schema
  edits beyond payload evolution.
- Documentation reiterates litigation hold is out of scope and highlights the
  audit endpoints for operational review.

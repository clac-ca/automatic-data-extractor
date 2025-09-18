# Current Task — Ship a simple, reusable audit log

## Goal
Create a single audit logging mechanism that ADE can reuse everywhere, starting
with document deletions, so we capture who did what and when without layering in
unnecessary infrastructure.

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

## Proposed design
- `audit_events` table keyed by ULID with:
  - `event_type` (string: `document.deleted`, `document.uploaded`, etc.).
  - `entity_type`, `entity_id` (strings) for cross-model coverage.
  - `occurred_at` UTC timestamp defaulting to `datetime.utcnow()`.
  - Optional actor columns: `actor_type`, `actor_id`, `actor_label`.
  - Optional origin info: `source` (API, scheduler, CLI) + `request_id`.
  - `payload` JSON column for event-specific context; ensure deterministic
    serialisation.
  - Indexes on `(entity_type, entity_id)` and `event_type` for filtered reads.
- `services/audit_log.py` exposing `record_event(event_type, *, entity_type,
  entity_id, actor=None, source=None, request_id=None, payload=None, session)`.
  Handle validation, ULID generation, timestamp defaulting, and JSON
  serialisation so callers remain simple.
- Document deletion pathways call `record_event(...)` once they mark the row as
  deleted. Guard against duplicates by checking the soft-delete state before
  logging.
- FastAPI endpoints:
  - `GET /audit-events` with filters for entity, event type, time range, and
    source/request ID.
  - `GET /documents/{document_id}/audit-events` convenience wrapper that locks
    `entity_type="document"` and `entity_id=document_id`.
- Pydantic response schema exposes the full event payload and clarifies that the
  JSON structure varies by event type.
- Tests cover manual + automatic deletion events, idempotent retries, payload
  round-tripping, and endpoint filtering behaviour.
- Update README, glossary, and retention guide with the new audit log concept
  and instructions for adding future event types.

## Definition of done
- Every deletion path emits a single `document.deleted` audit event accessible
  via the new endpoints; retries do not double-log.
- Operators can filter audit events to inspect document deletion history with
  actor/context metadata.
- Other teams know how to call `record_event(...)` for their own workflows
  without schema edits beyond payload evolution.
- Documentation reiterates that litigation hold is out of scope and highlights
  the audit endpoints for operational review.

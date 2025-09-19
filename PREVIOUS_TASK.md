# Previous Task — Expose configuration and job audit timelines

## Goal
Add focused API endpoints that return the audit history for a single configuration or job so the UI can render timelines without reimplementing filtering logic.

## Why this matters
- Configuration and job events now land in the shared audit log, but consumers still need a straightforward way to retrieve them for a specific entity.
- Dedicated endpoints keep pagination, filtering, and 404 handling consistent across entity types.
- These timelines unblock the next round of UI work (job detail pages, configuration history tabs) without duplicating SQL in route handlers.

## Proposed scope
1. **Configuration timeline endpoint** – Provide `GET /configurations/{configuration_id}/audit-events` that wraps `list_entity_events(...)`, supports pagination + filtering parameters, and returns 404 when the configuration does not exist.
2. **Job timeline endpoint** – Mirror the configuration endpoint with `GET /jobs/{job_id}/audit-events`, ensuring events are ordered newest-first and exposing the same filter knobs (`event_type`, `source`, `occurred_after`, `occurred_before`, etc.).
3. **Shared response shape** – Reuse `AuditEventListResponse` so all timeline endpoints line up. Consider small convenience helpers (e.g., translating FastAPI query params into the service call) to keep handlers minimal.
4. **Documentation and tests** – Add API tests covering success paths, pagination, missing-entity failures, and filter handling. Update README/glossary to mention the new endpoints and where to find per-entity timelines.

## Open questions / follow-ups
- Should the timeline endpoints also return a lightweight summary of the entity (title, status) to avoid an extra API call in the UI?
- Do we need to introduce an audit stream that correlates related entities (e.g., job events plus the originating document events) for richer timelines later?
- Is it worth threading request IDs or correlation IDs into responses now that the audit log stores them, or should that wait until the UI consumes them?

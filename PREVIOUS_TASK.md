# Previous Task — Include entity summaries in timeline responses

## Goal
Attach lightweight entity metadata to the configuration and job audit timeline responses so UI callers can render headers without making extra round trips.

## Why this matters
- The new per-entity audit endpoints return only events; the UI must currently request the configuration or job separately to display names and status.
- Including a minimal summary keeps the timeline API ergonomic for low-latency views while still reusing existing audit filters.
- Surfacing the summary in one response also makes it easier to log or debug requests without correlating multiple payloads.

## Proposed scope
1. **Schema updates** – Extend `AuditEventListResponse` or introduce a wrapper so `/configurations/{configuration_id}/audit-events` and `/jobs/{job_id}/audit-events` can include an `entity` block. For configurations capture `configuration_id`, `document_type`, `title`, `version`, and `is_active`; for jobs include `job_id`, `document_type`, `status`, and `created_by`.
2. **Endpoint wiring** – Load the entity once per request, reuse the existing event pagination logic, and populate the summary fields without disturbing other response attributes.
3. **Tests and docs** – Add API tests that assert the summary is present, stays in sync with the entity, and still returns 404 for missing resources. Update the README/glossary to mention the embedded metadata and how clients can rely on it.

## Open questions / follow-ups
- Should the document timeline mirror the same summary shape for consistency?
- Do we need to expose additional job details (e.g., configuration version, latest run status) to help timeline consumers?
- Would it be useful to embed a count of event types or timestamps for quick navigation tabs in the UI?

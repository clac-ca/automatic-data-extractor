# Current Task — Mirror entity summaries for document timelines

## Goal
Extend the document audit timeline endpoint so `/documents/{document_id}/audit-events` returns the same embedded `entity` summary pattern as configurations and jobs.

## Why this matters
- Timeline consumers currently get document metadata only by calling `/documents/{document_id}` separately; embedding the summary keeps the API ergonomic for quick views.
- Aligning all timeline responses unlocks shared UI components that expect an `entity` block without branching on entity type.
- The document summary gives operators enough context (filename, size, expiry) to investigate events straight from logs or CLI tools.

## Proposed scope
1. **Schema support** – Extend the `AuditEventListResponse.entity` union to include a document summary with `document_id`, `original_filename`, `content_type`, `byte_size`, `sha256`, and `expires_at`.
2. **Endpoint wiring** – Load the document once in `GET /documents/{document_id}/audit-events`, return 404 if missing, and attach the summary while preserving the existing pagination behaviour.
3. **Validation** – Add API tests that cover happy path, missing document, and ensure updates to document metadata (e.g., delete markers) are reflected in the embedded summary. Update the README/glossary to document the shared `entity` shape across timelines.

## Open questions / follow-ups
- Should the summary also surface deletion metadata (`deleted_at`, `deleted_by`) when present?
- Do we need a guard to prevent leaking metadata for documents marked as purged or expired?
- Once all timelines share an `entity` block, should we document a reusable client type for SDKs?

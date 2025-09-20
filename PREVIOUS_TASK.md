# Previous Task — Finalize document–job linking without legacy payloads

## Goal
Finish the schema and API work so jobs reference a single input document via `jobs.input_document_id`, documents optionally link back to the producing job with `documents.produced_by_job_id`, and job projections surface linked documents without carrying historical JSON blobs.

## Why this mattered
- The prior join/role abstractions were unnecessary and complicated pagination.
- Keeping relationships in first-class columns allows `/jobs`, `/documents`, and `/documents/{document_id}/jobs` to answer history questions directly.
- Dropping unused `legacy_input` plumbing keeps the codebase simpler before any production consumers rely on it.

## Scope
1. **Schema + models**
   - Ensure jobs store `input_document_id` and documents store `produced_by_job_id`, with supporting indexes.
   - Remove the unused `jobs.input` JSON column and any association tables.
2. **Services + routes**
   - Require a valid `input_document_id` when creating jobs and compute `input_document`/`output_documents` on read.
   - Let document uploads optionally set `produced_by_job_id`, expose the history view at `/documents/{document_id}/jobs`, and support filtering via `input_document_id`/`produced_by_job_id` query parameters.
   - Keep document downloads disabled for soft-deleted rows and surface deletion state in projections.
3. **Docs + tests**
   - Update README + glossary examples to describe the computed projection model.
   - Add pytest coverage for multiple outputs, deletion markers, history queries, list filters, and validation errors.

## Out of scope
- Frontend changes to consume the new response shapes.
- Processor/runtime changes beyond API surface area.
- Historical data migrations beyond the new columns.

## Acceptance criteria
- Job responses return `input_document` and `output_documents` summaries derived from the database pointers.
- Document uploads accept optional `produced_by_job_id` and reject unknown jobs.
- History endpoints and list filters operate on the new columns without exposing any legacy `input` payloads.

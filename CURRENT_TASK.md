# Current Task — Update the frontend for computed job/document projections

## Goal
Refresh the React UI and API client types to consume the new `input_document`/`output_documents` job payloads and the `DocumentJobsResponse` shape.

## Why this matters
- Backend responses no longer expose a `documents` array or `outputs` map; the UI currently expects those fields and will render empty states.
- Document detail pages should show the `input_to_jobs` and `produced_by_job` structure returned by `/documents/{document_id}/jobs`.
- Filters now use `input_document_id`/`produced_by_job_id`, so list views and client utilities must match the revised contract.

## Scope
1. **Client types + adapters**
   - Regenerate or hand-update TypeScript interfaces for jobs and document history endpoints.
   - Update the API client wrappers to pass `input_document_id`/`produced_by_job_id` query parameters where appropriate.

2. **UI surfaces**
   - Adjust job detail pages to render the `input_document` summary and `output_documents` list, including deleted state handling.
   - Update document history screens to display `input_to_jobs` entries and the optional `produced_by_job` summary.

3. **Regression pass**
   - Smoke-test job creation flows, document uploads, and history views against the updated backend.
   - Update any screenshots or documentation snippets that referenced the old `documents` field.

## Out of scope
- Backend API changes (already complete).
- Processor logic or scheduling adjustments.
- Authentication and broader UX improvements.

## Acceptance criteria
- UI renders linked input/output documents for jobs without console errors.
- Document detail pages show both consuming jobs and the producing job when present.
- Manual QA confirms filtering and navigation still work with the new query parameters.

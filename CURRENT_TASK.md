# Current Task — Link jobs to documents and expose history APIs

## Goal
Establish first-class relationships between uploaded documents and the jobs that consume them so the UI can show processing history per file.

## Why this matters
- The current schema stores job input URIs as free-form JSON, so there is no reliable way to answer "which jobs processed this document?" without parsing strings in application code. 【F:backend/app/models.py†L62-L126】【F:backend/app/services/jobs.py†L47-L196】
- ADE_GLOSSARY already calls out a planned `job_documents` join table, signalling the intent to formalise these links before the frontend goes live. 【F:ADE_GLOSSARY.md†L70-L84】
- Without explicit relationships the forthcoming frontend cannot show job history from a document detail view or highlight which documents fed a job, undermining operator workflows the README promises. 【F:README.md†L53-L103】

## Scope
1. **Schema + models**
   - Introduce a `JobDocument` association table (or equivalent) that records `job_id`, `document_id`, and the role of the relationship (e.g. `input`, `output`). 【F:ADE_GLOSSARY.md†L70-L84】
   - Update SQLAlchemy models, migrations, and Base metadata so the table is created alongside existing ones. 【F:backend/app/models.py†L16-L199】

2. **Service layer updates**
   - Extend `JobCreate`/`JobResponse` schemas to accept and emit referenced document IDs while remaining backward compatible for existing tests. 【F:backend/app/schemas.py†L195-L318】
   - Enhance `create_job` (and any helpers) to validate provided document IDs, populate the association table inside the same transaction, and ensure updates keep relationships intact. 【F:backend/app/services/jobs.py†L47-L196】
   - Decide how to infer document IDs when callers only pass a stored URI; document the expectation if we require the explicit ID going forward. 【F:backend/app/routes/jobs.py†L1-L147】

3. **HTTP surface**
   - Add `GET /documents/{document_id}/jobs` (and complementary filtering on `/jobs`) so clients can fetch jobs tied to a document without scanning every job. 【F:backend/app/routes/documents.py†L1-L202】【F:backend/app/routes/jobs.py†L1-L147】
   - Ensure the new endpoint reuses existing Pydantic responses and enforces 404s / pagination limits consistent with other timeline endpoints.

4. **Tests + docs**
   - Expand pytest coverage: job creation with document links, listing jobs for a document, rejecting unknown document IDs, and ensuring deletion/purge flows keep associations consistent. 【F:backend/tests/test_jobs.py†L1-L362】【F:backend/tests/test_documents.py†L1-L602】
   - Update README and glossary to describe the new relationships and endpoints so the frontend contract stays accurate. 【F:README.md†L53-L191】【F:ADE_GLOSSARY.md†L70-L130】

## Out of scope
- Processor changes for emitting derived output artefacts.
- UI work or API authentication.
- Full job-to-multiple-documents orchestration beyond storing the association and exposing read APIs.

## Acceptance criteria
- Jobs created through the API persist associations to existing documents, and those links are queryable via HTTP.
- Document and job payloads surface linked document IDs so the UI can render history without inferring from storage URIs.
- Existing routes and tests continue to pass, with new tests covering the added behaviour.

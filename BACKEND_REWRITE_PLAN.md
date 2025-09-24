# ADE Backend Rewrite – Architecture Notes

## Why this rewrite?
The previous FastAPI backend attempted to replicate the legacy system with a
message hub, timeline events, and a background worker abstraction. That design
was difficult to reason about and obscured the core product goal: upload a file,
run a deterministic extractor, and share the resulting tables. The rewrite
focuses on clarity, small internal-facing APIs, and deliberate expansion only
when the foundations are stable.

Key guardrails:

- Keep the codebase approachable for a small internal team.
- Prefer explicit services over implicit cross-module side effects.
- Preserve deterministic behaviour so extraction results are auditable.

## Core capabilities
The rebuilt backend will offer three core workflows:

1. **Document intake** – receive uploads, capture metadata, and store the file
   safely on disk.
2. **Job execution** – validate requested configuration, invoke the extractor
   synchronously (single worker process for now), and persist status updates.
3. **Result review** – expose stored tables and job logs so analysts can confirm
   the extraction output.

## Module boundaries
The FastAPI application will expose two primary domain modules backed by shared
infrastructure components:

| Module | Responsibility |
| ------ | -------------- |
| `documents` | Manage metadata, storage lifecycle, and download helpers. |
| `jobs` | Submit extraction runs, track status, and link inputs/outputs. |

Cross-cutting helpers will live outside the modules:

- `services.storage.DocumentStorage` – safe filesystem access rooted in
  `data/documents/` with streaming helpers using `run_in_threadpool`.
- `processor.run(job_request)` – deterministic extraction entry point returning
  structured tables and job metrics.
- `repositories.*` – thin SQLAlchemy wrappers used by services.

### Documents module sketch
- POST `/documents/` accepts uploads, validates size/type, writes to
  `DocumentStorage`, and persists metadata.
- GET `/documents/` lists the workspace catalogue.
- GET `/documents/{document_id}` returns metadata.
- DELETE `/documents/{document_id}` performs soft delete and schedules file
  cleanup (still synchronous in the first iteration).

_Status:_ Implemented in the current iteration with storage safeguards, audit events, and integration tests.

### Jobs module sketch
- POST `/jobs/` validates that the input document exists and the configuration
  is available, then dispatches the synchronous extractor.
- GET `/jobs/` lists recent jobs with status fields (`pending`, `running`,
  `succeeded`, `failed`).
- GET `/jobs/{job_id}` returns detailed metrics and any log entries.
- GET `/jobs/{job_id}/results` streams the extracted tables (served from the
  tables repository introduced in the previous rebuild).

## Data model checkpoints
- Reuse the existing `documents` and `jobs` tables for now so we can layer the
  new services without performing a migration mid-rewrite.
- Move timeline/event columns into simple status fields on the `jobs` table.
  Rich audit trails can be reintroduced after the core flow is stable.
- Continue to store extracted tables in `extracted_tables`, keeping the schema
  consistent with the current migrations.

## Processing lifecycle
1. Upload document (metadata stored, file persisted on disk).
2. Submit job referencing document + configuration version.
3. Job service writes a `jobs` row with status `pending`, then runs the extractor
   in-process.
4. On success the service persists extracted tables, updates status to
   `succeeded`, and records duration/row counts.
5. On failure the service captures the error, updates status to `failed`, and
   retains partial logs for debugging.

Background queue infrastructure will remain dormant until we have a strong case
for asynchronous execution. The single-process synchronous worker keeps the
implementation easy to understand during the rewrite.

## Upcoming milestones
1. Ship the synchronous jobs workflow (service + router + processor stub) so
   `/jobs` submissions validate inputs, run the extractor, and surface status
   transitions.
2. Refresh the results module once jobs emit table outputs, ensuring document
   and job timelines stay consistent.
3. Extend smoke coverage to span upload → job → results using the stub
   extractor to guard the new flow.
4. Formalise retention follow-ups (purge/TTL policies) now that soft deletion
   removes stored files immediately.

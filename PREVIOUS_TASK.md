## Context
Phase 4 progressed from worker scaffolding to persisting extraction outputs end-to-end.

## Outcome
- Added an `extracted_tables` model, Alembic migration, repository, service, and router so jobs and documents can list extracted tables via `/jobs/{job_id}/tables` and `/documents/{document_id}/tables` with access control.
- Enhanced the job worker to persist stub extraction outputs, clear stale artefacts, emit `job.outputs.persisted` hub events, and record table summaries alongside status updates.
- Expanded integration coverage to assert table persistence, document/job timeline events, and 404 handling for unknown jobs, tables, and documents while updating the processor stub to produce deterministic output.

## Context
Implemented the first functional slice of the rewritten documents workflow so
uploads, catalog queries, and downloads operate end-to-end on the new backend
foundation.

## Outcome
- Added `backend/app/services/storage.py` with a `DocumentStorage` adapter that
  confines file access to `settings.documents_dir`, enforces safe path
  resolution, and streams blocking I/O via `run_in_threadpool`.
- Rebuilt the `documents` module with a service + router pair that handles
  upload/list/detail/download/delete endpoints, emits audit events, and wires in
  workspace-aware access control.
- Replaced the placeholder pytest module with targeted unit and integration
  coverage for storage helpers and the documents HTTP API (happy paths and error
  cases such as oversize uploads and missing files).

## Next steps
- Rebuild the synchronous jobs workflow so `/jobs` can submit extraction runs,
  resolve document/configuration inputs, and persist status transitions.
- Update the results module once the new job lifecycle is in place so table
  retrieval routes operate against the rewritten job engine.
- Document retention follow-ups (purge/TTL) now that soft deletion removes the
  backing file immediately.

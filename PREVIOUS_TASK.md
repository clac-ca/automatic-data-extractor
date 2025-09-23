## Context
Phase 4 began by needing an event dispatcher and the first domain module rebuilt on top of the new authentication and workspace context. We had to wire a message hub through the application so future services and background jobs can react to document lifecycle events.

## Outcome
- Introduced `backend/app/core/message_hub.py` with subscribe/publish semantics, registered it on application startup, and exposed a `BaseService.publish_event` helper that enriches payloads with correlation, actor, and workspace metadata.
- Updated the service context to carry the hub so module services can emit events consistently, keeping the FastAPI request state and dependency stack in sync.
- Scaffolded the `documents` module (SQLAlchemy model, repository, service, dependencies, router, exceptions) with read-only list/detail endpoints guarded by `workspace:documents:read` and emitting hub events for analytics.
- Added integration tests seeding documents, asserting the new endpoints return data, and verifying message hub handlers receive `documents.listed`/`document.viewed` events alongside negative coverage for 404 responses.

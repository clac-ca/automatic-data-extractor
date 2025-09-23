## Context
Phase 4 now needed durable event storage so downstream workflows can audit document activity and surface timelines through the API. The message hub already emitted events, but nothing persisted them to the `events` table or exposed a consumer-facing endpoint.

## Outcome
- Created an `events` module with SQLAlchemy model, repository, service dependency, and an `EventRecorder` subscriber that translates hub messages into persisted rows via an async session factory.
- Updated the application factory to instantiate the recorder, subscribe it to the hub, and cleanly unsubscribe on shutdown.
- Extended the documents service to annotate emitted events with entity metadata, optionally suppress view events, and provide a read-only `/documents/{document_id}/events` timeline backed by a shared events service.
- Added integration coverage ensuring document views populate the timeline endpoint and 404s are returned for unknown documents, re-running the full backend test suite.

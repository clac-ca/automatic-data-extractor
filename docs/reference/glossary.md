# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`backend/api/modules/documents`](../../backend/api/modules/documents). Stored bytes live under the configured `storage_documents_dir`.

## Job
An extraction request that consumes an input document and configuration revision. Job submission and monitoring routes are defined in [`backend/api/modules/jobs`](../../backend/api/modules/jobs). Background execution relies on the task queue in [`backend/api/core/task_queue.py`](../../backend/api/core/task_queue.py).

## Result
Structured tables produced by a completed job. Fetch them through [`backend/api/modules/results`](../../backend/api/modules/results) using either a job ID or document ID.

## Configuration
Versioned extraction logic referenced by jobs. Configuration CRUD endpoints sit in [`backend/api/modules/configurations`](../../backend/api/modules/configurations), while the active revision is resolved during job submission.

## Workspace
A logical tenant boundary enforced by [`backend/api/modules/workspaces`](../../backend/api/modules/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## Event
Immutable audit records persisted by [`backend/api/modules/events`](../../backend/api/modules/events) and the recorder service in [`backend/api/modules/events/recorder.py`](../../backend/api/modules/events/recorder.py). Events track actions across documents, jobs, configurations, and security operations.

## API Key
A long-lived credential provisioned for automation clients via routes in [`backend/api/modules/auth`](../../backend/api/modules/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

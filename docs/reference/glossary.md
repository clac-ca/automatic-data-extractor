# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`app/documents`](../../app/documents). Stored bytes live under the configured `storage_documents_dir`.

## Job
An extraction request that consumes an input document and configuration revision. Job submission and monitoring routes are defined in [`app/jobs`](../../app/jobs). Background execution relies on the task queue in [`app/core/task_queue.py`](../../app/core/task_queue.py).

## Result
Structured tables produced by a completed job. Fetch them through [`app/results`](../../app/results) using either a job ID or document ID.

## Configuration
Versioned extraction logic referenced by jobs. Configuration CRUD endpoints sit in [`app/configurations`](../../app/configurations), while the active revision is resolved during job submission.

## Workspace
A logical tenant boundary enforced by [`app/workspaces`](../../app/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## Event
Immutable audit records persisted by [`app/events/recorder.py`](../../app/events/recorder.py) using the repository helpers in [`app/events/repository.py`](../../app/events/repository.py). Events track actions across documents, jobs, configurations, and security operations.

## API Key
A long-lived credential provisioned for automation clients via routes in [`app/auth`](../../app/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

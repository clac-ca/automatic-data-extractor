# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`app/features/documents`](../../app/features/documents). Stored bytes live under the configured `storage_documents_dir`.

## Job
An extraction request that consumes an input document and configuration revision. Job submission and monitoring routes are defined in [`app/features/jobs`](../../app/features/jobs). Background execution relies on the task queue in [`app/services/task_queue.py`](../../app/services/task_queue.py).

## Configuration
Versioned extraction logic referenced by jobs. Configuration CRUD endpoints sit in [`app/features/configurations`](../../app/features/configurations), while the active revision is resolved during job submission.

## Workspace
A logical tenant boundary enforced by [`app/features/workspaces`](../../app/features/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## API Key
A long-lived credential provisioned for automation clients via routes in [`app/features/auth`](../../app/features/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

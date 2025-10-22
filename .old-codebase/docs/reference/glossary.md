# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`ade/features/documents`](../../ade/features/documents). Stored bytes live under the configured `storage_documents_dir`.

## Job
An extraction request that consumes an input document and configuration revision. Job submission and monitoring routes are defined in [`ade/features/jobs`](../../ade/features/jobs). Background execution relies on the in-process queue defined in [`ade/workers/task_queue.py`](../../ade/workers/task_queue.py).

## Configuration
Versioned extraction logic referenced by jobs. Configuration CRUD endpoints sit in [`ade/features/configurations`](../../ade/features/configurations), while the active revision is resolved during job submission.

## Workspace
A logical tenant boundary enforced by [`ade/features/workspaces`](../../ade/features/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## API Key
A long-lived credential provisioned for automation clients via routes in [`ade/features/auth`](../../ade/features/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

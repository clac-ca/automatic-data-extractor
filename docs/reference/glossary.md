# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`apps/api/app/features/documents`](../../apps/api/app/features/documents). Stored bytes live under the configured `storage_documents_dir`.

## Job
An extraction request that consumes an input document and configuration revision. Job submission and monitoring routes are defined in [`apps/api/app/features/jobs`](../../apps/api/app/features/jobs). Execution happens inline through the pluggable processor contract exposed by [`apps/api/app/features/jobs/processor.py`](../../apps/api/app/features/jobs/processor.py).

## Configuration
Workspace-scoped packages containing draft files, manifests, and published snapshots. Configuration APIs live in [`apps/api/app/features/configs`](../../apps/api/app/features/configs), while jobs reference a concrete `config_version_id`.

## Workspace
A logical tenant boundary enforced by [`apps/api/app/features/workspaces`](../../apps/api/app/features/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## API Key
A long-lived credential provisioned for automation clients via routes in [`apps/api/app/features/auth`](../../apps/api/app/features/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

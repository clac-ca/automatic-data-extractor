# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`backend/app/features/documents`](../../backend/app/features/documents). Stored bytes live under the configured `storage_documents_dir`.

## Job
An extraction request that consumes an input document and the workspace's active configuration. Job submission and monitoring routes are defined in [`backend/app/features/jobs`](../../backend/app/features/jobs). Each run executes the sandboxed detect→assign→transform pipeline driven by the configuration's column modules and hooks.

## Configuration
Workspace-scoped, file-backed bundles rooted at `data/configs/<config_id>/`. Each configuration folder contains a manifest, optional hook scripts, and one Python module per canonical output column. Metadata such as title, status (`active`, `inactive`, or `archived`), checksums, and ownership resides in the database while the manifest and code live on disk. Configuration APIs live in [`backend/app/features/configs`](../../backend/app/features/configs).

## Workspace
A logical tenant boundary enforced by [`backend/app/features/workspaces`](../../backend/app/features/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## API Key
A long-lived credential provisioned for automation clients via routes in [`backend/app/features/auth`](../../backend/app/features/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

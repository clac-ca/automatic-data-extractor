# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`apps/ade-api/src/ade_api/features/documents`](../../apps/ade-api/src/ade_api/features/documents). Stored bytes live in Azure Blob under `workspaces/<workspace_id>/files/<file_id>`. Documents are `files` rows with `kind=input`, and immutable byte history is stored in `file_versions`. `name_key` is the internal, normalized key used for uniqueness.

## Document version
An immutable snapshot of document bytes stored in the `file_versions` table. Versions are numbered per document (`version_no`) and retain storage metadata like hashes, size, content type, and storage version ID.

## Change feed
The realtime stream of document changes backed by the `document_changes` table. It is designed for UI refresh workflows (notify + fetch) and has short retention (currently ~14 days).

## Audit log
An optional, append-only history table for long-lived compliance or debugging use cases. ADE does not enable an audit log by default; it can be added later if required.

## Run
An extraction request that consumes an input document and configuration revision. Run submission and monitoring routes are defined in [`apps/ade-api/src/ade_api/features/runs`](../../apps/ade-api/src/ade_api/features/runs). Execution happens inline through the pluggable processor contract exposed by [`apps/ade-api/src/ade_api/features/runs/processor.py`](../../apps/ade-api/src/ade_api/features/runs/processor.py).

## Configuration
Workspace-scoped configuration packages with a lifecycle of `draft` → `active` → `archived`. Configuration APIs live in [`apps/ade-api/src/ade_api/features/configs`](../../apps/ade-api/src/ade_api/features/configs), while runs reference a concrete `configuration_id`.

## Workspace
A logical tenant boundary enforced by [`apps/ade-api/src/ade_api/features/workspaces`](../../apps/ade-api/src/ade_api/features/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspaceId}/documents`) so dependencies can scope database queries appropriately.

## API Key
A long-lived credential provisioned for automation clients via routes in [`apps/ade-api/src/ade_api/features/auth`](../../apps/ade-api/src/ade_api/features/auth). Hashes are stored in the database and usage is tracked via `last_used_at`.

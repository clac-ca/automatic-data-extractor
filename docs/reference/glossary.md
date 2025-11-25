# Glossary

Shared terminology used across the Automatic Data Extractor API, database, and UI.

## Document
A file uploaded through the documents API. Metadata and lifecycle operations are handled by [`apps/ade-api/src/ade_api/features/documents`](../../apps/ade-api/src/ade_api/features/documents). Stored bytes live under the configured `documents_dir`.

## Run
An extraction request that consumes an input document and configuration revision. Run submission and monitoring routes are defined in [`apps/ade-api/src/ade_api/features/runs`](../../apps/ade-api/src/ade_api/features/runs). Execution happens inline through the pluggable processor contract exposed by [`apps/ade-api/src/ade_api/features/runs/processor.py`](../../apps/ade-api/src/ade_api/features/runs/processor.py).

## Configuration
Workspace-scoped packages containing draft files, manifests, and published snapshots. Configuration APIs live in [`apps/ade-api/src/ade_api/features/configs`](../../apps/ade-api/src/ade_api/features/configs), while runs reference a concrete `config_version_id`.

## Workspace
A logical tenant boundary enforced by [`apps/ade-api/src/ade_api/features/workspaces`](../../apps/ade-api/src/ade_api/features/workspaces). Workspace identifiers are part of the URL path (for example `/workspaces/{workspace_id}/documents`) so dependencies can scope database queries appropriately.

## API Key
A long-lived credential provisioned for automation clients via routes in [`apps/ade-api/src/ade_api/features/auth`](../../apps/ade-api/src/ade_api/features/auth). Hashes are stored in the database, and usage is throttled via the `session_last_seen_interval` setting.

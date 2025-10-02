# Work Package: Document Type Summary API

## Objective
Provide a workspace-scoped endpoint that lists document types with active configuration metadata so the frontend rail and detail views can render consistent taxonomy.

## Deliverables
- Canonical document-type source (either a new table or deterministic derivation) linked to each workspace.
- Service/repository helpers that return document type metadata including `display_name`, `status`, and `active_configuration_id`.
- New API route (likely under `/workspaces/{id}/document-types`) delivering the summary payload defined in the frontend design.
- Tests covering empty states, single/multiple types, and permission enforcement.

## Key Decisions
- Start with a table `workspace_document_types` storing `document_type`, `display_name`, `status`, and `active_configuration_id`; keep version history out of scope.
- Drive `status` from configuration availability: `active` when an active configuration exists, `draft` otherwise.
- Defer metrics (success rates, pending jobs) to the metrics work package, but structure the response to accept those fields.

## Tasks
1. Design and apply Alembic migration(s) introducing the document type table linked to `workspaces`.
2. Add SQLAlchemy model + Pydantic schema for document type summaries.
3. Implement repository/service helpers to list document types for a workspace, joining on configurations for active IDs.
4. Expose a FastAPI route (e.g., `/workspaces/{workspace_id}/document-types`) that returns the list.
5. Cover scenarios with pytest (permissions, empty list, active/draft combinations).

## Testing
- pytest covering new repository/service/route logic.
- mypy to ensure types align.

## Out of Scope
- Aggregated metrics (handled by `WP_WORKSPACE_METRICS`).
- UI/front-end changes.
- Bulk editing UI or admin CRUD.

## Dependencies
- Requires `WP_WORKSPACE_DATA_MODEL` to ensure documents/configurations are workspace-scoped.

## Frontend impact
- Workspace rail and document-type detail routes in `agents/FRONTEND_DESIGN.md` rely on `/workspaces/{workspace_id}/document-types` returning `DocumentTypeSummary` (names, status, active configuration). Without this payload the SPA cannot populate navigation or breadcrumbs.

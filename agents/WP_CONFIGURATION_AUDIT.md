# Work Package: Configuration Audit Metadata

## Objective
Augment configuration records with publisher metadata and draft state so the frontend configuration drawer can display version history and publish controls.

## Deliverables
- Alembic migration adding `published_by`, `published_at`, and `draft_state` (boolean or status) columns to configurations.
- Service logic that records publisher info when activating configurations and preserves revision breadcrumbs.
- API responses exposing the new fields (`ConfigurationRecord` schema updates).
- Tests covering activation flows, draft saves, and audit trail retrieval.

## Key Decisions
- Record publisher information using the current authenticated user ID and timestamp in UTC.
- Represent draft state with a boolean `is_draft` or enum; default to `False` for published versions.
- Avoid building full version history APIs in this package—surface metadata through existing routes.

## Tasks
1. Design and apply migration altering the configurations table with the new audit columns (include backfill defaults).
2. Update SQLAlchemy model and Pydantic schema to expose the fields.
3. Modify configuration activation/update services to populate publisher metadata and toggle draft state.
4. Adjust tests to assert the new fields and add coverage for audit behaviour.
5. Run pytest + mypy.

## Testing
- pytest targeting configuration service/router suites.
- mypy for schema/service updates.

## Out of Scope
- UI changes.
- External audit reporting endpoints.
- Version diff tooling.

## Dependencies
- Depends on `WP_WORKSPACE_DATA_MODEL` to ensure configuration records are workspace-aware before audit metadata expansion.

## Frontend impact
- Configuration drawer requires `published_by`, `published_at`, `draft` state, and revision notes per `agents/FRONTEND_DESIGN.md`. Current `ConfigurationRecord` omits these fields, so publish/save controls cannot reflect real state.

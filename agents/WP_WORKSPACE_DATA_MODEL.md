# Work Package: Workspace Data Model

## Objective
Create first-class workspace scoping across documents, configurations, jobs, and extraction results so every request is owned by exactly one workspace.

## Deliverables
- Alembic migrations that add `workspace_id` foreign keys (ULID strings) to the `documents`, `configurations`, `jobs`, and `extracted_tables` tables, enforce `NOT NULL`, add indexes, and apply `ON DELETE CASCADE`.
- Updated SQLAlchemy models and Pydantic schemas reflecting the new fields.
- Service/repository updates that require the active workspace context for CRUD and ensure cross-workspace access is impossible.
- Workspace-aware factory helpers/fixtures in tests to keep coverage green.

## Key Decisions
- Use existing `workspace_memberships.workspace_id` values as authoritative identifiers; reuse the same ULIDs.
- Enforce data integrity via foreign keys referencing `workspaces.workspace_id`.
- Because we can break compatibility, migrations may drop existing rows that lack workspace ownership after recording a console warning, then set `nullable=False` immediately.

## Tasks
1. Draft Alembic migration(s) to add `workspace_id` columns and foreign-key constraints, with backfill logic.
2. Update SQLAlchemy models (`app/documents/models.py`, `app/configurations/models.py`, `app/jobs/models.py`, `app/results/models.py`) to include the new relationship/column.
3. Extend repositories/services to require the active workspace ID and filter queries accordingly; raise 404/403 when mismatched.
4. Adjust FastAPI dependencies to inject workspace ID where missing; update unit/integration tests.
5. Run pytest + mypy to confirm the refactor is safe.

## Testing
- pytest (focus on documents/configurations/jobs/results suites).
- mypy for typing regressions.

## Out of Scope
- Analytics/metrics derivations.
- Frontend changes.
- New REST endpoints (covered in later packages).

## Dependencies
- Existing workspace membership handling stays as-is (ULID primary keys with `workspace_memberships` join table and explicit roles); we simply ensure all downstream data references that owner workspace.

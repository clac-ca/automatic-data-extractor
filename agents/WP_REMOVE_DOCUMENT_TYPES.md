# Work Package: Remove Document Type Layer

## Status
- **Owner:** Core Platform Guild
- **Last Reviewed:** 2025-10-14
- **State:** _Discovery_
- **Notes:** Plan the end-to-end refactor that collapses the extra “document type” abstraction so each workspace owns a single configuration lineage.

## Objective
- Treat the workspace as the unit of classification for ADE. Configuration management, job execution, and copy should no longer reference a nested document type concept.
- Simplify API contracts so clients create and activate configurations without providing or filtering by `document_type`.
- Deliver a deterministic migration path that preserves existing configuration history and jobs while preparing operators to split mixed workspaces into dedicated ones if needed.

## Background
- `Configuration` records currently carry a `document_type` column and unique constraint (`workspace_id`, `document_type`, `version`) (`ade/features/configurations/models.py`). Services, repositories, and routers pass the value through (`ade/features/configurations/service.py`, `ade/features/configurations/repository.py`, `ade/features/configurations/router.py`, `ade/features/configurations/schemas.py`).
- Job rows stamp the same string and forward it to processors (`ade/features/jobs/models.py`, `ade/features/jobs/service.py`, `ade/features/jobs/schemas.py`). Tests exercise this path (`ade/features/jobs/tests/test_router.py`, `ade/features/jobs/tests/test_service.py`).
- The Alembic baseline creates `document_type` columns and scoped indexes in both `configurations` and `jobs` tables (`ade/alembic/versions/0001_initial_schema.py`).
- Frontend copy and design guidance still talk about configuring document types inside a workspace (`frontend/src/app/workspaces/sections.ts`, `frontend/src/app/routes/WorkspacesIndexRoute.tsx`, `agents/FRONTEND_DESIGN.md`, `agents/WP_FRONTEND_REBUILD.md`).
- Documentation echoes the terminology (`docs/user-guide/README.md`). Automated tests and fixtures rely on it (`ade/db/tests/test_session.py`, `ade/features/configurations/tests/test_router.py`).

## Proposed Direction
### Data model
- Drop the `document_type` column from `configurations` and `jobs`, update the unique constraint to `("workspace_id", "version")`, and replace indexes scoped by document type with workspace-oriented equivalents.
- Simplify activation logic so only one configuration can be active per workspace; deactivate siblings using `workspace_id` alone.
- Retire document-type-specific exceptions in favour of workspace-scoped errors (for example `ActiveConfigurationNotFoundError` referencing `workspace_id`).

### Services & API
- Remove `document_type` parameters from repository and service methods; update contracts to accept only `workspace_id`, configuration metadata, and optional `is_active` filters.
- Amend FastAPI routes to stop exposing `document_type` query params or response fields. Update `ConfigurationRecord`/`ConfigurationCreate` schemas and OpenAPI summaries to use workspace-centric language.
- Ensure job submission payloads, job records, and processor wiring no longer depend on document-type metadata.

### Processor integration
- Continue providing downstream processors the full configuration payload plus metadata (`workspace_id`, configuration identifiers). If processors need additional hints, expose them explicitly in the `metadata` block rather than reintroducing document-type strings.

### Terminology & UX
- Replace document-type references in frontend strings and design docs with workspace-focused messaging. Confirm navigation plans in `agents/FRONTEND_DESIGN.md` and `agents/WP_FRONTEND_REBUILD.md` stay coherent once document types disappear.
- Review help content and onboarding copy to clarify that new document formats require creating a new workspace.

### Documentation & Tooling
- Update `docs/user-guide/README.md`, `README.md`, and any runbooks to describe the simplified model.
- Add developer notes on the migration path (workspace audits, versioning expectations) to `docs/` or `agents/` as appropriate.

## Migration Considerations
- Inventory production data to confirm whether any workspace currently hosts configurations spanning multiple document types. Provide guidance for splitting them into separate workspaces before the schema change, or script a data migration that clones workspace metadata safely.
- Create a reversible Alembic script (even though the baseline file is edited) that can snapshot the legacy values before deleting the column, so support can recover or inspect prior document-type assignments if needed.
- Communicate rollout sequencing: update APIs and clients in lockstep, delay column removal until runtime behaviour no longer references the field, and add temporary guards that reject requests still supplying `document_type`.

## Milestones & Tasks
### M0 – Discovery & Alignment
1. Confirm stakeholder agreement that every future document format maps 1:1 with a workspace and document-type terminology should disappear from UI and docs.
2. Audit live datasets (or representative fixtures) for mixed workspaces; document remediation steps for operations.
3. Baseline automated tests that currently assert document-type behaviour to ensure they are updated rather than deleted.

### M1 – Schema & Domain Updates
1. Adjust `ade/alembic/versions/0001_initial_schema.py` to drop `document_type` columns and rebuild indexes/constraints.
2. Update ORM models, repositories, services, and exceptions in `ade/features/configurations/` and `ade/features/jobs/` to remove document-type parameters.
3. Regenerate payload shaping and validation tests in `ade/features/configurations/tests/test_router.py`, `ade/features/jobs/tests/test_router.py`, and `ade/features/jobs/tests/test_service.py`.

### M2 – API & Processor Behaviour
1. Simplify FastAPI routers so configuration endpoints only filter by status or activation, and job submission returns records without document-type fields.
2. Update job processor wiring to exclude document-type context and ensure processors receive `workspace_id`, configuration identifiers, and payloads consistently.
3. Extend regression tests (pytest + httpx) to guarantee no route accepts or returns document-type data.

### M3 – Frontend & Documentation Refresh
1. Swap frontend copy and placeholders in `frontend/src/app/workspaces/sections.ts` and `frontend/src/app/routes/WorkspacesIndexRoute.tsx` to describe the workspace-as-format model.
2. Align `agents/FRONTEND_DESIGN.md`, `agents/WP_FRONTEND_REBUILD.md`, and public docs with the new terminology.
3. Publish updated user guidance that instructs customers to create new workspaces for distinct document formats.

### M4 – Rollout & Cleanup
1. Stage the schema change in lower environments, verifying migrations, API responses, and job execution logs.
2. Monitor job processor behaviour and configuration activation in staging; confirm existing jobs continue to succeed without document-type metadata.
3. Remove any temporary compatibility shims and close the loop with stakeholders once production is stable.

## Acceptance Criteria
- Configuration APIs, models, and persisted records no longer store or expose a `document_type` field.
- Jobs execute successfully with the reduced schema; job records omit document-type data and processors still receive necessary context.
- Automated tests (unit, integration, and API) cover versioning, activation, and job submission without document-type parameters.
- Frontend UI and documentation consistently instruct users to create a new workspace when handling a new format.
- Migration notes capture how to audit and remediate workspaces that previously hosted multiple document types.

## Testing & QA
- Run `pytest`, `ruff`, and `mypy` to confirm backend integrity. Update or add fixtures covering workspace-scoped configuration activation and job execution.
- Execute end-to-end httpx tests for configuration lifecycle and job submission to ensure no lingering document-type references.
- Plan manual validation for staging: create a workspace, upload documents, create/activate configurations, submit jobs, and verify processor payloads.

## Risks & Mitigations
- **Mixed workspaces:** Existing tenants may hold multiple document types; mitigate by auditing ahead of time and supplying migration tooling.
- **Downstream processors relying on document_type:** Confirm no third-party integrations parse the field; if any do, provide an alternative metadata key before removal.
- **Client drift:** Older frontend builds or API clients might still send `document_type`; add temporary validation that rejects the field with a clear error before the schema change deploys.

## Open Questions
- Do we need to preserve the legacy document-type value in an audit log or history table for compliance?
- Should we expose workspace metadata (e.g., intended format name) to processors to replace the document-type string, or rely solely on configuration payloads?
- How should we coordinate workspace splitting for tenants with mixed document types—tooling, support runbook, or manual guidance?


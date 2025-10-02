# Work Package: Workspace Metrics & Status Strip

## Objective
Provide lightweight analytics endpoints that compute the hero metric (`documents_processed_7d`), success rates, pending job counts, and recent alerts so the workspace shell and document type detail can surface operational health.

## Deliverables
- Materialized SQL queries or service helpers that compute seven-day document throughput, success rates over recent jobs, and pending job counts per document type.
- API responses that attach these metrics to workspace and document-type summaries (either by extending existing endpoints or exposing dedicated routes).
- Tests validating calculations, time windows, and edge cases (no data, stale data).

## Key Decisions
- Perform calculations on demand using efficient SQL (window functions) before introducing background aggregation.
- Standardize the “past seven days” window using UTC timestamps.
- Treat “pending jobs” as jobs with `status in ('pending', 'running')` scoped to the current workspace/document type.

## Tasks
1. Add repository helpers that compute seven-day processed document counts and job success rates per workspace/document type.
2. Extend service layer to merge these metrics into the document type summary payload (depends on `WP_DOCUMENT_TYPE_SUMMARY`).
3. Provide hero metric on the workspace endpoint (could be `/workspaces/{id}` or a dedicated `/workspaces/{id}/metrics`).
4. Write unit/integration tests covering fresh data, empty datasets, and mixed success/failure jobs.
5. Update documentation/playbooks to describe the metrics contract.

## Testing
- pytest focusing on new metric helpers and endpoint coverage.
- mypy to ensure types align.

## Out of Scope
- Long-term historical analytics dashboards.
- Frontend implementation.
- Background jobs for aggregation.

## Dependencies
- Depends on `WP_WORKSPACE_DATA_MODEL` and `WP_DOCUMENT_TYPE_SUMMARY` for consistent workspace/document scoping.

## Frontend impact
- Hero metrics and the document-type status strip depend on the aggregates described here (7-day throughput, success rate, pending jobs, recent alerts). Until these fields are added to workspace and document-type APIs, sections 8.2 and 8.3 of `agents/FRONTEND_DESIGN.md` cannot render as designed.

# Frontend next task — Workspace job orchestration

## Objective
Extend the workspace experience beyond document ingestion by letting analysts submit extraction jobs, monitor progress, and review job detail without leaving the app shell. Synchronise the document-type filter between the top bar and job surfaces so filters remain consistent.

## Why this matters
- Uploads now flow end-to-end, but analysts cannot yet trigger ADE processing or see job state, blocking the core value proposition.
- Backend routes for jobs, logs, and metrics already exist, meaning the frontend can light up job management without extra API work.
- Sharing the persisted document-type filter across documents, jobs, and results keeps analysts oriented as they switch contexts.

## Suggested scope
1. Promote the document-type selector into the top bar, backed by the existing localStorage preference and active-configuration query, so downstream routes can read the current filter.
2. Add React Query hooks for `GET /workspaces/{workspaceId}/jobs`, `POST /workspaces/{workspaceId}/jobs`, and job detail polling while status is non-terminal.
3. Build a jobs list page with status chips, document-type filter chips, and quick links back to source documents and configurations.
4. Implement a "Run extraction" modal/drawer that reuses the document picker, allows choosing one or more configurations, validates inputs, and posts to the jobs endpoint with toast feedback.
5. Create a job detail view surfacing metadata, metrics, logs, and follow-up actions (download tables, re-run) with graceful empty/error states.
6. Expand Vitest coverage for the new hooks, submission form validation, and polling behaviour, plus adjust the component test utilities for the top-bar filter.

## Definition of done
- Analysts can submit a job from uploaded documents, see it appear in the jobs list, and monitor status transitions without manual refresh.
- Failed jobs surface actionable messaging, and completed jobs link to downstream results placeholders.
- The document-type filter stays in sync between the top bar, documents table, and jobs list.
- `npm run lint`, `npm run test`, and `npm run build` pass locally.

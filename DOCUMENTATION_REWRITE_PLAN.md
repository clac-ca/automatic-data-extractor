# Documentation Rewrite Plan

## Intent
- Replace the current documentation with a clean, GitHub‑first structure centred on two personas:
  - User Guide (everyday usage: upload, process, download results)
  - Admin Guide (install, configure, secure, operate)
- Remove `DOCUMENTATION.md` and `DOCUMENTATION_CURRENT_TASK.md` once the new structure lands.
- Keep content minimal but actionable, with direct links to code and API examples.
- Rewrite the project root `README.md` to reflect the new structure and quickstart.
- House all guide content under `docs/` so GitHub surfaces a single entry point.

## Principles
- Single source of truth in the repo (no external wikis).
- GitHub‑friendly: every directory gets a `README.md` index for natural navigation.
- Persona‑first: Users shouldn’t need admin docs and vice‑versa.
- Deterministic, auditable steps; mirror ADE’s clarity and simplicity priorities.

## Proposed Structure (GitHub rendered)
- `README.md` (project root)
  - Rewritten to introduce ADE, core concepts (documents → jobs → results), and point to `docs/` guides.
- `docs/README.md`
  - Landing page describing how documentation is organised, with quick links to User and Admin guides.
- `docs/user-guide/README.md` (index)
  - `docs/user-guide/authentication.md` – login methods and tokens.
  - `docs/user-guide/workspaces.md` – `X-Workspace-ID` header and membership.
  - `docs/user-guide/documents.md` – upload, list, download, delete.
  - `docs/user-guide/jobs.md` – submit jobs, list jobs, view events.
  - `docs/user-guide/results.md` – fetch extracted tables by job/document.
  - `docs/user-guide/examples.md` – cURL and HTTP examples for common flows using sample assets from `examples/`.
- `docs/admin-guide/README.md` (index)
  - `docs/admin-guide/install.md` – Python version, uvicorn run, Alembic, quick health check (`GET /health`).
  - `docs/admin-guide/configuration.md` – settings, env vars, docs toggle, file storage.
  - `docs/admin-guide/security.md` – auth modes, API keys, SSO, docs exposure.
  - `docs/admin-guide/database.md` – migrations, URLs, pooling, backups.
  - `docs/admin-guide/operations.md` – logs, correlation IDs, in-process job queue, message hub/events fan-out, retention knobs, health endpoints.
  - `docs/admin-guide/troubleshooting.md` – common errors with actionable fixes.
- Optional later: `docs/api/README.md` – link to `/openapi.json`, SDK notes, schema change policy.
- Link to `ADE_GLOSSARY.md` from root and guide indexes for shared terminology.

## Content Map → Code (coverage checklist)
- Authentication
  - Password grant and SSO flows: `backend/app/modules/auth/router.py:AuthRoutes`.
  - API keys admin endpoints: same file; header `X-API-Key` convention in security utils.
  - Output models: `backend/app/modules/auth/schemas.py:TokenResponse`.
- Workspaces & permissions
  - Context binding and header: `backend/app/modules/workspaces/dependencies.py:bind_workspace_context`.
  - Example permission checks: `backend/app/modules/workspaces/router.py:WorkspaceRoutes`.
- Documents
  - CRUD & download flows: `backend/app/modules/documents/router.py`.
  - Payload models and error enums: `backend/app/modules/documents/schemas.py` and `.../exceptions.py`.
- Jobs
  - Submit/list/get & events: `backend/app/modules/jobs/router.py`.
  - Processing worker: `backend/app/modules/jobs/worker.py`.
- Results
  - Tables by job/document: `backend/app/modules/results/router.py`.
- Events
  - Recording and dispatch: `backend/app/modules/events/recorder.py`, `.../service.py`.
- Configuration (current → near‑term)
  - Current settings model: `backend/app/core/settings.py:get_settings`.
  - Planned Dynaconf: `DYNACONF_MIGRATION_PLAN.md` (link from Admin Guide until migration lands).
- App wiring and docs toggle
  - App factory & docs URLs: `backend/app/main.py: create_app`.
  - Logging level setup: `backend/app/core/logging.py:setup_logging`.
- Database
  - Engine/session and pooling: `backend/app/db/engine.py`, `backend/app/db/session.py`.
  - Migrations runner: `backend/app/migrations/env.py` and `alembic.ini`.
- Middleware & request context
  - Correlation IDs, structured request logs: `backend/app/extensions/middleware.py` and `backend/app/core/logging.py`.
- Task queue & jobs
  - In‑process queue semantics and subscribers: `backend/app/core/task_queue.py`, `backend/app/modules/jobs/worker.py`.

## Draft Page Outlines

- Root `README.md`
  - One‑paragraph elevator pitch, architecture sketch (text + ASCII or image later), capabilities, links to Admin/User Guides, and a 60‑second local run (uvicorn) snippet.

- docs/user-guide (each topic ≤ one screen, examples first)
  - authentication.md
    - Token endpoint with `application/x-www-form-urlencoded`, SSO login → callback, and API key usage; include cURL for each.
  - workspaces.md
    - Explain header `X-Workspace-ID`, how to fetch memberships, and how permissions influence routes.
  - documents.md
    - Upload (multipart), list with pagination, download with `FileResponse` headers, soft delete and metadata update; cURL blocks.
  - jobs.md
    - Submit job, list jobs, view job events; reference common failure modes from router exceptions.
  - results.md
    - List tables for job or document; show stable output fields.
  - examples.md
    - End‑to‑end flow: upload → create job → poll → fetch tables; copy‑paste cURL sequence using sample assets from `examples/`.

- docs/admin-guide
  - install.md
    - Python 3.11, virtualenv, `uvicorn backend.app.main:app --reload`, Alembic upgrade, and quick health check (`GET /health`).
  - configuration.md
    - Current settings (Pydantic) and near‑term Dynaconf plan; how to toggle docs, adjust upload limits, paths (`data_dir`, `documents_dir`).
  - security.md
    - API keys issuance/revocation (admin‑only), SSO envs and cookie behaviour, disable `/docs` in non‑local.
  - database.md
    - URLs, pooling options, SQLite vs. Postgres notes, migration commands.
  - operations.md
    - Logs (JSON), request correlation IDs, in‑process job queue (no separate worker needed), message hub/events fan-out, retention knobs, health endpoints.
  - troubleshooting.md
    - 413 upload too large, 401/403 workspace permission errors, 404 document/job/config not found, SSO callback issues.

## Authoring Conventions
- Use folder `README.md` as index; keep pages short with task‑based headings.
- Prefer cURL snippets with environment variables (`$ADE_TOKEN`, `$WORKSPACE_ID`).
- Add “At a glance” tables only where they improve scanability; otherwise bullets.
- Link to code with GitHub‑friendly paths (e.g., `backend/app/modules/documents/router.py:1`).
- Use blockquotes for callouts (tips, warnings) to keep Markdown portable.
- Keep examples copy‑pastable; avoid placeholders that don’t run.

## Migration Steps (docs only)
1. Remove the existing `docs/` directory (after archiving anything worth keeping) to start clean.
2. Scaffold the new structure under `docs/` (`README.md`, `user-guide/`, `admin-guide/`, optional `api/`).
3. Author the pages listed above with cURL examples and minimal prose.
4. Rewrite the project root `README.md` with the new quickstart and links to `docs/`.
5. Remove `DOCUMENTATION.md` and `DOCUMENTATION_CURRENT_TASK.md` once new guides are in place.
6. Open issues to track post‑migration improvements (images, API reference page, Dynaconf updates).

## Rationale & Trade‑offs
- Persona split keeps each audience in their lane, shortening time‑to‑task.
- Keeping docs in‑repo enables fast, reviewable iteration and aligns with ADE’s deterministic ethos.
- Minimal surface (few pages, short files) improves maintenance and reduces drift.
- GitHub rendering + directory READMEs gives intuitive navigation without extra tooling.
- Linking to source lines and keeping examples short reduces drift between code and docs.

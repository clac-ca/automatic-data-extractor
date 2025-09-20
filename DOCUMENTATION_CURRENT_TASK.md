# Documentation plan: seed persona-aligned docs with current backend features

## Goal
Establish the first slice of persona-focused documentation that matches the structure in `DOCUMENTATION.md` using capabilities that already exist in the repository (FastAPI backend, configuration lifecycle, authentication, document retention, and eventing). This iteration should create the doc hub, migrate the in-scope legacy docs into the new layout, and add a few high-value guides so future contributors can expand coverage without rewriting the structure again.

## Deliverables (execute in order)

1. **Create the documentation skeleton and navigation hub**
   - Add `docs/README.md` as the documentation landing page with the required front-matter block (`Audience`, `Goal`, `Prerequisites`, `When to use`, `Validation`, `Escalate to`). Audience should be "All personas". Introduce the five persona cards described in `DOCUMENTATION.md`, each linking to the README inside its folder and listing 2–3 key guides/runbooks that will exist after this task.
   - Create the folder structure: `docs/foundation/`, `docs/platform/`, `docs/security/`, `docs/configuration/`, `docs/operations/`, `docs/operations/runbooks/`, `docs/data-integration/`, `docs/reference/`, `docs/user-guide/`, and `docs/assets/`. Every directory should receive a short `README.md` with front-matter and a concise description of the section scope plus recommended reading order.
   - Add `docs/assets/README.md` with an empty table or bullet list for tracking diagrams/screenshots later. Mention that entries should note the asset filename, owning doc, and date last validated.
   - Update the root `README.md` "Documentation" or "System overview" section to link prominently to `docs/README.md` so GitHub visitors discover the new hub. Leave the rich architectural content in place for now; only add the navigation pointer.

2. **Foundation overview**
   - Migrate the high-level architecture material from the root `README` into `docs/foundation/system-overview.md`. Include the metadata front-matter targeting Platform Administrators and IT Architects. Summarise the Dockerized architecture, component responsibilities, lifecycle of a job, and how events/documents relate. Reference the glossary instead of duplicating definitions (link to `../ADE_GLOSSARY.md`). Keep or recreate the ASCII architecture diagram; note where a future diagram asset will live.
   - In `docs/foundation/README.md`, give a short introduction, link to `system-overview.md`, `../ADE_GLOSSARY.md`, and highlight other foundational references (health endpoint, identifier strategy). Clarify that deeper deployment and security guidance lives in their respective sections.

3. **Security & authentication**
   - Transform `docs/authentication.md` into `docs/security/authentication-modes.md`. Add front-matter for Platform Administrators/Security. Preserve the environment variable matrix, CLI commands, password hashing details, and login flow, but restructure with task-focused headings (e.g., "Choose an auth mode", "Configure session cookies", "Manage users", "Understand the login flow"). Ensure the doc references `backend/app/config.py`, `backend/app/auth/manage.py`, and `backend/app/auth/sessions.py` for provenance.
   - Author `docs/security/sso-setup.md` with front-matter for Platform Administrators. Cover prerequisites (OIDC provider, redirect URL), configuration variables, how discovery/JWKS caching behaves (pull from `backend/app/auth/sso.py`), and recovery steps (rotating secrets/keys, clearing caches via the CLI or restart). Include validation steps: hit `/auth/sso/login`, inspect logs, and confirm events (`user.sso.login.*`).
   - Update `docs/security/README.md` to summarise the available guides (`authentication-modes.md`, `sso-setup.md`) and point to future runbooks (e.g., SSO outage recovery) as TODOs.

4. **Configuration lifecycle guides**
   - Convert `docs/configuration_lifecycle.md` into two persona guides under `docs/configuration/`:
     - `concepts.md`: explain immutable versions, draft/active/retired states, and the event families emitted. Tie each concept to concrete API endpoints from `backend/app/routes/configurations.py` and schemas in `backend/app/schemas.py`.
     - `publishing-and-rollback.md`: task-focused walkthrough for creating a draft (`POST /configurations`), promoting it (`PATCH … is_active=true`), and rolling back (activating a previous version). Document validation steps (e.g., check `GET /configurations/active/{document_type}`, inspect events). Include escalation guidance when no active configuration exists.
   - Adjust `docs/configuration/README.md` to introduce the section, list the two guides above, and record future placeholders (`authoring-guide.md`, `validation-and-testing.md`, `import-export.md`) as TODOs with a one-line description each so later contributors know the expected coverage.

5. **Document retention & purge operations**
   - Relocate `docs/document_retention_and_deletion.md` content into `docs/operations/document-retention.md`. Keep policy details (default window, overrides, scheduler behaviour) but add the metadata front-matter for Platform Administrators and Support. Reference the relevant code (`backend/app/config.py`, `backend/app/services/documents.py`, `backend/app/maintenance/autopurge.py`, `backend/app/routes/health.py`).
   - Create `docs/operations/runbooks/expired-document-purge.md` following the runbook template (Triggers → Diagnostics → Resolution → Validation → Escalation). Describe manual CLI usage (`python -m backend.app.maintenance.purge`), how to interpret summaries, and when to disable/re-enable the scheduler. Link back to the policy guide above.
   - Update `docs/operations/README.md` to point to the policy doc and runbook, and list future runbooks (storage capacity, SSO outage) as TODO placeholders.

6. **Data integration quick start**
   - Add `docs/data-integration/README.md` (front-matter: Data teams) introducing API and SQL access expectations, emphasising that API coverage exists today while SQL/reporting will follow.
   - Write `docs/data-integration/api-overview.md` summarising the REST endpoints currently implemented (`/auth/login`, `/documents`, `/configurations`, `/jobs`, `/events`, `/health`). For each endpoint family, include: purpose, required auth, key request parameters, and link to the relevant schema models. Reuse example payloads from the root README where accurate, but adapt them to the new layout and point back to `ADE_GLOSSARY.md` for field definitions. Close with validation steps (use `httpx` or `curl` examples) and escalation notes.

7. **Reference material**
   - Create `docs/reference/environment-variables.md` compiling the settings exposed in `backend/app/config.py`. Organise by theme (database, documents, purge scheduler, auth, SSO). Note defaults, allowed values, and whether a restart is required. Include validation guidance (e.g., check `/health` for purge status after changing scheduler settings).
   - Seed `docs/reference/README.md` with links to the environment variable matrix and placeholders for upcoming references (API schema/OpenAPI, CLI command index, release notes). Mention automation expectations (e.g., keep tables synced with source files).

8. **Clean up legacy docs**
   - Remove `docs/authentication.md`, `docs/configuration_lifecycle.md`, and `docs/document_retention_and_deletion.md` after their content is migrated to avoid duplication. Ensure redirects or links in the new docs account for the new locations.

## Out of scope for this iteration
- End-user UI walkthroughs or screenshots (frontend not present yet).
- Detailed processor authoring guides, diff/history tooling, or import/export workflows that rely on unfinished features.
- Infrastructure/hosting docs beyond the authentication and purge content listed above.

## Source material to consult while authoring
- Backend FastAPI routes and services: `backend/app/routes/*.py`, `backend/app/services/*.py`, `backend/app/auth/*.py`, `backend/app/maintenance/*.py`.
- Schemas for response shapes: `backend/app/schemas.py`.
- Configuration defaults: `backend/app/config.py`.
- Existing narrative context: `README.md`, `ADE_GLOSSARY.md`, and the legacy docs being migrated.

## Definition of done
- All new/updated Markdown files include the mandated metadata block and relative links resolve correctly when viewed on GitHub.
- Persona navigation works: every card on `docs/README.md` points to live content and each section README lists its guides/runbooks.
- Obsolete docs are removed, and `git status` shows no stray files. Run `pytest -q` to confirm documentation work didn’t disturb the backend environment.

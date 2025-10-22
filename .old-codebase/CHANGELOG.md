# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Deliver workspace chrome toggles and a redesigned documents page with filters, grid/list views, bulk actions, and an inspector drawer.
- Introduce an Angular workspace directory service with loading and error states to power the app shell navigation.
- Rebuild the ADE frontend in `frontend/` with a Vite/React workspace shell, focus mode, inspector context, and document/configuration surfaces.
- Add a stubbed telemetry helper (`trackEvent`) to prepare for backend event collection.
- Introduce a command palette (`⌘K` / `Ctrl+K`) and refined navigation chrome inspired by best-in-class productivity apps.
- Enable document uploads and deletions directly from the Documents page with API-backed mutations, toasts, and inspector download shortcuts.
- Introduce configuration column and script-version tables with matching ORM and Pydantic models to back the configuration authoring flows.
- Ship a configuration workspace UI with version management, column editing, and script authoring complete with validation previews and docstring parsing.

### Changed
- Run Angular unit tests against a Puppeteer-managed Chrome Headless binary so contributors do not need a system Chrome install.
- Rename the backend package to ``ade`` and update defaults, documentation, and tooling to use the new ``data/`` storage root.
- Simplify the ADE settings module to use direct BaseSettings fields with clearer path resolution and OIDC/cors parsing.
- Relocate the ADE settings module to ``ade/settings.py`` and update imports and docs to match the new location.
- Require confidential OIDC clients, retain the `ADE_AUTH_SSO_AUTO_PROVISION` toggle (defaulting to true), and remove the unused domain controls.
- Simplify SSO discovery by removing in-process metadata and JWKS caches in favour of per-request fetches.
- Drop configurable provider lists; `/auth/providers` now surfaces the default SSO option whenever OIDC is enabled.
- Align `ade start` with `uvicorn ade.app:create_app --factory`, make reload opt-in, and fix the Windows exit bug when running without reload.
- Relocate Alembic migrations to `ade/db/migrations/` and let the engine manage bootstrap/metadata loading for autogenerate.
- Introduce per-feature service dependencies and repositories (documents, configurations, jobs, users, health) to keep routers thin, scaffold system-settings helpers for future admin flows, and mount the v1 router from `ade/v1/router.py`.
- Replace the legacy workspace layout with a four-zone navigation model (top bar, collapsible left rail, main surface, optional inspector) and persist per-workspace chrome state.
- Simplify router spine: remove remote-mounted AppShell chrome, render workspace nav/top bar inside `WorkspaceLayout`, and gate private routes with a plain session-guarded Outlet.
- Adopt React Router framework mode with file-based routes, replace the manual `AppRouter` with generated routes, and inline the workspace documents screen under `src/app/routes`.
- Collapse legacy feature route wrappers into `src/app/routes/**`, keep `/workspaces/:id/configurations` as the canonical path, and hang detail pages off shared layout segments.
- Move workspace navigation/top-bar/layout helpers into `src/app/routes/workspaces/$workspaceId/` and standardise feature API clients under `features/*/api/client.ts` with barrel re-exports.
- Polish navigation chrome with a workspace summary card, document-focused left rail (All/Recent/Pinned/Archived), settings relocated to the profile menu, a sticky header shadow, body scroll locking for overlays, and accessibility tweaks to the command palette inspired by modern productivity apps.
- Sort status columns according to the workspace spec and gate destructive/bulk actions with loading states and dismissible feedback banners.
- Fetch documents via the v1 API with enlarged batch sizes, surface backend download streams with filename parsing, and show inline loading across inspectors and menus while files are retrieved.
- Refine document uploads with drag-and-drop handling, client-side filtering of supported formats, and clearer status messaging during manual uploads.
- Surface a workspace upload progress tray that lists in-flight files while backend uploads run, keeping drag-and-drop and picker flows transparent.
- Validate configuration scripts inside a sandboxed subprocess with size limits, timeouts, and network isolation.

### Removed
- Remove the legacy `ade/main.py` and `ade/settings.py` compatibility shims now that the app and config live under `ade/app.py` and `ade/platform/config.py`.
- Drop `ade/db/bootstrap.py`; bootstrap now lives inside the engine/session modules.
- Drop the placeholder “Connect source” affordances from the documents surface to keep the MVP focused on manual uploads.

### Fixed
- Ensure document uploads stream to the backend API, clear progress indicators per file, and immediately refresh the workspace list after completion.
- Fix the upload picker so selected files are processed before the input resets, keeping button and drag-and-drop uploads consistent.
- Automatically refresh browser sessions before access tokens expire so idle users are not met with unexpected 401 errors.
- Fix SPA navigation not re-rendering: dedupe React/React Router in Vite and redesign navigation so workspace chrome lives inside the workspace route; sidebar highlights, breadcrumbs, and main panel now update immediately on click.

## [v0.1.0] - 2025-10-09

### Added
- Initial release of ADE with the FastAPI backend, CLI utilities, and frontend build pipeline.

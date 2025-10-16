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

### Changed
- Run Angular unit tests against a Puppeteer-managed Chrome Headless binary so contributors do not need a system Chrome install.
- Rename the backend package to ``ade`` and update defaults, documentation, and tooling to use the new ``data/`` storage root.
- Simplify the ADE settings module to use direct BaseSettings fields with clearer path resolution and OIDC/cors parsing.
- Relocate the ADE settings module to ``ade/settings.py`` and update imports and docs to match the new location.
- Require confidential OIDC clients, retain the `ADE_AUTH_SSO_AUTO_PROVISION` toggle (defaulting to true), and remove the unused domain controls.
- Simplify SSO discovery by removing in-process metadata and JWKS caches in favour of per-request fetches.
- Drop configurable provider lists; `/auth/providers` now surfaces the default SSO option whenever OIDC is enabled.
- Align `ade start` with `uvicorn ade.main:create_app --factory`, make reload opt-in, and fix the Windows exit bug when running without reload.
- Replace the legacy workspace layout with a four-zone navigation model (top bar, collapsible left rail, main surface, optional inspector) and persist per-workspace chrome state.
- Polish navigation chrome with a workspace summary card, document-focused left rail (All/Recent/Pinned/Archived), settings relocated to the profile menu, a sticky header shadow, body scroll locking for overlays, and accessibility tweaks to the command palette inspired by modern productivity apps.
- Sort status columns according to the workspace spec and gate destructive/bulk actions with loading states and dismissible feedback banners.
- Fetch documents via the v1 API with enlarged batch sizes, surface backend download streams with filename parsing, and show inline loading across inspectors and menus while files are retrieved.
- Refine document uploads with drag-and-drop handling, client-side filtering of supported formats, and clearer status messaging during manual uploads.
- Surface a workspace upload progress tray that lists in-flight files while backend uploads run, keeping drag-and-drop and picker flows transparent.

### Removed
- Drop the placeholder “Connect source” affordances from the documents surface to keep the MVP focused on manual uploads.

### Fixed
- Ensure document uploads stream to the backend API, clear progress indicators per file, and immediately refresh the workspace list after completion.

## [v0.1.0] - 2025-10-09

### Added
- Initial release of ADE with the FastAPI backend, CLI utilities, and frontend build pipeline.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Introduce an Angular workspace directory service with loading and error states to power the app shell navigation.

### Changed
- Run Angular unit tests against a Puppeteer-managed Chrome Headless binary so contributors do not need a system Chrome install.
- Rename the backend package to ``ade`` and update defaults, documentation, and tooling to use the new ``data/`` storage root.
- Simplify the ADE settings module to use direct BaseSettings fields with clearer path resolution and OIDC/cors parsing.
- Relocate the ADE settings module to ``ade/settings.py`` and update imports and docs to match the new location.
- Require confidential OIDC clients, retain the `ADE_AUTH_SSO_AUTO_PROVISION` toggle (defaulting to true), and remove the unused domain controls.
- Simplify SSO discovery by removing in-process metadata and JWKS caches in favour of per-request fetches.
- Drop configurable provider lists; `/auth/providers` now surfaces the default SSO option whenever OIDC is enabled.
- Align `ade start` with `uvicorn ade.main:create_app --factory`, make reload opt-in, and fix the Windows exit bug when running without reload.

## [v0.1.0] - 2025-10-09

### Added
- Initial release of ADE with the FastAPI backend, CLI utilities, and frontend build pipeline.

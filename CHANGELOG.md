# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Introduce a shared right-aligned drawer primitive for workspace chrome flows.

### Changed
- Refine the workspace document type detail view with a responsive header, status strip, and configuration drawer.
- Extract the document type detail layout into a shared provider so drawer state and future actions live behind one context.
- Rename the backend package to ``ade`` and update defaults, documentation, and tooling to use the new ``data/`` storage root.
- Simplify the ADE settings module to use direct BaseSettings fields with clearer path resolution and OIDC/cors parsing.
- Relocate the ADE settings module to ``ade/settings.py`` and update imports and docs to match the new location.

## [v0.1.0] - 2025-10-09

### Added
- Initial release of ADE with the FastAPI backend, CLI utilities, and frontend build pipeline.

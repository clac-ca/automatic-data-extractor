# WP0 — Preflight: Embed Templates

## Goal
Guarantee ADE ships built-in config-package templates straight from the backend so later work packages can assume the templates live beside the API code.

## Scope
* Relocate `templates/config-packages/*` into `apps/api/app/templates/config_packages/*`.
* Ensure `apps/api/pyproject.toml` (and any relevant build/publish target) includes `templates/config_packages/**` as package data.
* Refresh developer docs to reference the new path and remove mention of template databases or environment variables.

## Deliverables
1. Files physically present under `apps/api/app/templates/config_packages/<template_id>/`.
2. Packaging metadata updated so builds/wheels include the templates folder.
3. Documentation updates (README + `01-config-packages.md`) pointing to the new location.

## Acceptance
* Building the backend wheel/container results in templates being available via `importlib.resources`.
* No environment variable or external DB is needed to resolve templates.
* If this work already landed, mark WP0 complete and proceed to WP1.

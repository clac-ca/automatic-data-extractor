# WP3 — Lifecycle Actions: Activate / Archive / Clone

## Goal
Enforce a simple config lifecycle with exactly one active config per workspace and provide endpoints to activate, archive, and clone configurations.

## Scope
* Add a partial unique index to `configurations`: `UNIQUE(workspace_id) WHERE status='active'`.
* Implement lifecycle endpoints:
  * `POST /{config_id}/activate`
  * `POST /{config_id}/archive`
  * `POST /{config_id}/clone`

## Activate Behavior
* Allowed from `draft` or `inactive` → `active`.
* Re-validate the config tree.
* Compute and persist `content_digest` over `pyproject.toml`, `manifest.json`, `src/ade_config/**`, and optional `config.env`.
* Increment `config_version` (first activation bumps `0 → 1`).
* Demote the previous active config (if any) to `inactive`.
* Optional body `{ "ensure_build": true }` triggers WP5 build warming after state flips.

## Archive Behavior
* `POST /archive` sets status to `inactive` (read-only) without touching files.

## Clone Behavior
* `POST /clone` uses the WP1 copy/validate/promote pipeline to produce a new **draft** in the same workspace.
* Response mirrors WP1’s `POST` output.

## Acceptance
* DB enforces one active config per workspace.
* Activating, archiving, or cloning updates metadata timestamps appropriately.
* Activation stores `content_digest` + bumped `config_version`.
* `clone` paths contain full copies with `config_version=0` and `status='draft'`.

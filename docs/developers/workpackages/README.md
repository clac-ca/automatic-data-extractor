# Work Packages — Config Authoring, Builds, and Jobs

These work packages break the config lifecycle into focused efforts that line up with the developer guides:

* [01-config-packages.md](../01-config-packages.md) — how configs are structured, edited, and validated.
* [02-build-venv.md](../02-build-venv.md) — how builds create isolated virtual environments and how jobs consume them.
* [README.md](../README.md) — repo-wide overview tying frontend, backend, engine, and config layers together.

Follow the packages in order unless a prerequisite is already complete:

| WP | Title | Summary |
| -- | ----- | ------- |
| [WP0](./wp0-preflight-embed-templates.md) | Preflight: Embed Templates | Ensure backend ships config templates inside `apps/api/app/templates/config_packages/` and update packaging docs. |
| [WP1](./wp1-config-create-from-template.md) | Config Metadata & Draft Creation | Add DB metadata and APIs to create draft configs from templates or clones via copy/validate/promote. |
| [WP2](./wp2-draft-file-editing.md) | Draft File Editing API | CRUD endpoints for draft files with ETags, safe paths, and size limits. |
| [WP3](./wp3-lifecycle-actions.md) | Lifecycle Actions | Activate/archive/clone configs with one active per workspace and digest/version tracking. |
| [WP4](./wp4-import-from-upload.md) | Import from Upload | Pipeline to upload, scan, and promote archives into draft configs. |
| [WP5](./wp5-build-system.md) | Build System: DB & Builder | Persistent build records, venv creation, dedupe, healing, and pruning. |
| [WP6](./wp6-jobs-integration.md) | Jobs Integration | Run jobs in ensured builds and store `build_id` on job rows. |
| [WP7](./wp7-observability-housekeeping.md) | Observability & Housekeeping | Logging, sweeps, and documentation updates to close the loop. |
| [WP8](./wp8-config-files-api-v2.md) | Config Files API v2 | Typed list, uniform writes, and atomic rename for a race‑safe, cache‑friendly builder API. |

The intent is to keep each package independently testable while funneling all creation/edit/build flows through a single, auditable path rooted in the backend templates directory.

# WP7 — Observability, Housekeeping & Docs

## Goal
Make the end-to-end config/build/job system easy to operate through structured logs, periodic sweeps, and updated documentation.

## Observability
* Emit structured logs for:
  * Config creation/edit operations (including ETag conflicts).
  * Lifecycle actions (activate/archive/clone).
  * Build events (start/install/verify/activate/prune/fail) with durations.
* Capture lightweight metrics counters/timers for builds, edits, activations, and pruning.

## Housekeeping
* On startup, sweep `${ADE_CONFIGS_DIR}` for stale `.creating-*` directories and remove them safely.
* Periodically sweep build folders to:
  * Delete orphans with no DB rows.
  * Mark stale `building` rows as failed (reusing WP5 logic).

## Documentation
* Update `docs/developers/01-config-packages.md` to describe the server-side authoring flow and lifecycle actions.
* Update `docs/developers/02-build-venv.md` with DB-based dedupe, wait/timeout behavior, self-healing, and pruning details.
* Add `docs/developers/00-config-router.md` (or equivalent) summarizing the config endpoints, lifecycle, and unified creation pipeline.

## Acceptance
* Logs make it straightforward to trace creation → edit → build → job.
* Startup sweeps leave the workspace dirs clean without touching active configs/builds.
* Docs accurately explain how to create, activate, build, run, and troubleshoot configs end-to-end.

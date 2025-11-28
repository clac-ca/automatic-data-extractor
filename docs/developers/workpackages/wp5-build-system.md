# WP5 — Build System: DB, Builder, Ensure (build_id folders + pointer)

## Goal
Track per-configuration virtual environments in SQL, build them deterministically, deduplicate concurrent builders, self-heal failures, and prune unused environments.

## Scope
* Create `configuration_builds` table to persist build metadata.
* Manage virtual environments under `${ADE_VENVS_DIR}/{workspace}/{config}/{build_id}/` (default `/tmp/ade-venvs` on local storage).
* Provide an `ensure_build()` service used by both API endpoints and run submission.
* Implement REST endpoints to inspect, trigger, or delete builds.

## Database
`configuration_builds` columns:
* `(workspace_id, config_id, build_id)` primary key
* `status` (`building|active|inactive|failed`)
* `venv_path`
* `config_version` or `content_digest`
* `engine_version`, `python_version`
* `started_at`, `built_at`, `expires_at?`, `last_used_at?`
* `error TEXT NULL`

Constraints:
* Partial unique index: one `active` per `(workspace_id, config_id)`.
* Partial unique index: at most one `building` per `(workspace_id, config_id)`.

## Settings
Environment variables to honor (with defaults from the build guide):
* `ADE_VENVS_DIR` (default `/tmp/ade-venvs`)
* `ADE_PIP_CACHE_DIR` (`./data/cache/pip`)
* `ADE_ENGINE_SPEC` (`apps/ade-engine/`)
* `ADE_PYTHON_BIN` (optional override)
* `ADE_BUILD_TIMEOUT_SECONDS` (default `600`)
* `ADE_BUILD_ENSURE_WAIT_SECONDS` (default `30`)
* `ADE_BUILD_TTL_DAYS` (optional)
* `ADE_BUILD_RETENTION_DAYS` (optional, e.g., `7`)

## Service Behavior
`ensure_build(workspace, config, force=False)`:
1. Inspect `configuration_builds` for an `active` pointer.
2. Rebuild when: no active row, digest/version mismatch, engine/python version change, TTL expired, or `force=True`.
3. Deduplicate by inserting/updating a `status="building"` row (unique constraint guarantees one builder).
4. If a build is already running:
   * Runs path waits up to `ADE_BUILD_ENSURE_WAIT_SECONDS` for it to finish, otherwise returns `409 build_in_progress`.
   * UI path returns `200 {"status":"building"}` immediately.
5. Heal stale builders (`now - started_at > timeout`): mark failed, delete partial folder.
6. New builds:
   * Create venv at `…/{build_id}/`.
   * Install ADE Engine (`ADE_ENGINE_SPEC`) + workspace config package.
   * Verify imports: `python -I -B -c "import ade_engine, ade_config"`.
   * On success: flip previous active row to `inactive`, mark new row `active`.
   * On failure: delete folder, set row to `failed` with error.
7. After success/failure, prune inactive/failed builds older than `ADE_BUILD_RETENTION_DAYS` and not referenced by queued/running runs.

## API
* `GET /workspaces/{workspace}/configurations/{config}/build` → current pointer or `404`.
* `PUT /workspaces/{workspace}/configurations/{config}/build` Body `{ "force": false }`
  * Returns pointer, `"status":"building"`, or `409 build_in_progress` depending on caller behavior.
* `DELETE /workspaces/{workspace}/configurations/{config}/build`
  * Removes the active build if no runs reference it; otherwise `409`.

## Acceptance
* Multiple build requests coalesce into a single actual build per config.
* Crash mid-build is healed automatically on the next ensure.
* Rebuild can occur while runs still reference the previous `build_id`; new runs switch after pointer flip.
* Old build folders are pruned safely once unreferenced.

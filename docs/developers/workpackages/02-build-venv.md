# Work Package — Build Virtual Environments (build_id folders + DB pointer)

**Goal (what we’re doing):**
Implement per‑configuration Python virtual environments identified by a `build_id`. Each build is a separate folder on disk; the database stores which `build_id` is the **active pointer** for a given `(workspace_id, config_id)`. Jobs always run in the venv of the `build_id` they were assigned. The system deduplicates concurrent build attempts in the DB (no file locks), heals stale “building” states after crashes, enforces timeouts, and safely prunes old builds not referenced by jobs.

---

## Checklist (execute in order)

### 1) Settings & Defaults

* [ ] Add/confirm settings with sane defaults:

  * `ADE_VENVS_DIR` (default `./data/.venv`)
  * `ADE_PIP_CACHE_DIR` (default `./data/cache/pip`)
  * `ADE_ENGINE_SPEC` (default `packages/ade-engine/`)
  * `ADE_PYTHON_BIN` (optional; default system `python`)
  * `ADE_BUILD_TIMEOUT_SECONDS` (default `600`)
  * `ADE_BUILD_ENSURE_WAIT_SECONDS` (default `30`)
  * `ADE_BUILD_TTL_DAYS` (optional; unset by default)
  * `ADE_BUILD_RETENTION_DAYS` (optional; e.g., `7`)
* [ ] Expose normalized `Path` objects in the app’s `Settings` for services/builders (no direct env reads elsewhere).
* [ ] Update `.env.example` and docs to reflect these.

### 2) Database Schema & Repos

* [ ] Create `configuration_builds` table (one row **per build**):

  * Columns: `workspace_id`, `config_id`, `build_id` (ULID/UUIDv7), `status` (`building|active|inactive|failed`), `venv_path`, `config_version` (or `content_digest`), `engine_version`, `python_version`, `started_at`, `built_at`, `expires_at?`, `last_used_at?`, `error?`.
  * **PK**: `(workspace_id, config_id, build_id)`.
  * **Partial unique index**: one **active** per `(workspace_id, config_id)`.
  * **Partial unique index**: at most one **building** per `(workspace_id, config_id)`.
* [ ] Add to `jobs`: `build_id` (and optionally `engine_version`, `python_version` snapshot).
* [ ] Implement repository methods:

  * get active pointer, get by `(ws,cfg,build_id)`
  * insert `building` row, flip to `active`, mark `inactive|failed`
  * bump `last_used_at`
  * list prune candidates (inactive/failed, unreferenced)
  * detect **stale building** rows (`now - started_at > ADE_BUILD_TIMEOUT_SECONDS`)

### 3) Build Folder Layout & Path Safety

* [ ] Folder structure: `${ADE_VENVS_DIR}/{workspace_id}/{config_id}/{build_id}/`

  * Contains `bin/python` and site‑packages with `ade_engine`, `ade_config`.
* [ ] Sanitize `workspace_id` and `config_id` to safe path segments (no `..`, no separators).
* [ ] Ensure parent dirs exist with restrictive perms.

### 4) Fingerprint & Rebuild Triggers

* [ ] Implement `needs_rebuild` using:

  * missing active pointer, or
  * changed `config_version`/`content_digest`, or
  * changed `engine_version`, or
  * changed `python_version` (minor), or
  * TTL expired, or
  * `force=true`.
* [ ] Store these fields on each build row.

### 5) Concurrency (DB‑gated dedupe; no file locks)

* [ ] On `ensure_build(ws,cfg)`:

  * Check for **stale building** row; if stale ⇒ mark `failed` and remove partial folder (if present).
  * If **building exists** (not stale): wait up to `ADE_BUILD_ENSURE_WAIT_SECONDS` for pointer to become `active`; else return a retriable `build_in_progress` error (HTTP `409` from API).
  * If **no active & no building** and `needs_rebuild` ⇒ create new `building` row and proceed.

### 6) Builder (single build execution)

* [ ] Allocate `build_id`; set `target = ADE_VENVS_DIR/ws/cfg/build_id/`; insert `building` row with `started_at=now`.
* [ ] Create venv (`${ADE_PYTHON_BIN:-python} -m venv "${target}"`).
* [ ] Install:

  * `pip install --upgrade pip wheel`
  * `PIP_CACHE_DIR=... pip install ${ADE_ENGINE_SPEC}`
  * `PIP_CACHE_DIR=... pip install <config package dir>`
  * (optional) install `requirements.txt` overlay if present/supported.
* [ ] Verify imports within the new interpreter: `python -I -B -c "import ade_engine, ade_config"`.
* [ ] Capture `engine_version` and `python_version`.
* [ ] On any failure: delete `target`, set row `failed` with concise `error`, propagate error.

### 7) Activation & Pruning

* [ ] On success (transactional):

  * mark previous `active` (if any) ⇒ `inactive`
  * mark new build ⇒ `active` and set `built_at`, `expires_at?`
* [ ] After activation (and/or periodic sweep):

  * prune builds with `status in ('inactive','failed')` **and** not referenced by any jobs with state `queued|running` **and** older than `ADE_BUILD_RETENTION_DAYS`.
  * delete both folder and DB row.
* [ ] Startup housekeeping:

  * remove orphan folders (no DB row)
  * mark **stale** `building` rows `failed` and remove their folders.

### 8) Service & API

* [ ] Service: `ensure_build(ws,cfg, force=False) -> BuildPointer`

  * applies triggers, dedup, timeouts, stale healing, builder run, activation, pruning
  * returns `{workspace_id, config_id, build_id, venv_path, engine_version, python_version, status, built_at, expires_at?}`
* [ ] API Routes:

  * `GET  /api/v1/workspaces/{ws}/configurations/{cfg}/build` → active pointer or 404 if none yet
  * `PUT  /api/v1/workspaces/{ws}/configurations/{cfg}/build` (body: `{ "force": false }`)

    * returns `200` with pointer (or `"status":"building"` behavior if you choose to return immediately)
    * returns `409` if build in progress and server choose not to wait (depends on caller)
  * `DELETE /api/v1/workspaces/{ws}/configurations/{cfg}/build`

    * refuse with `409` if any job (queued|running) references active build
    * else delete folder + rows (next ensure will rebuild)
* [ ] Ensure OpenAPI schemas are minimal and consistent (`BuildPointer`).

### 9) Jobs Integration

* [ ] On job submit (server‑side):

  * call `ensure_build(ws,cfg)`
  * persist `build_id` (+ optional `engine_version`, `python_version`) on job row
  * launch worker via `${venv_path}/bin/python -I -B -m ade_engine.worker <job_id>`
* [ ] Update job codepaths to **never** install packages at runtime.

### 10) Timeouts, Liveness, & Crash Recovery

* [ ] Enforce **build timeout** using `ADE_BUILD_TIMEOUT_SECONDS` (kill/stop build; mark `failed`; delete partial folder).
* [ ] Enforce **ensure wait** using `ADE_BUILD_ENSURE_WAIT_SECONDS` (coalesce short bursts; avoid stampede).
* [ ] **Self‑heal** stale `building` rows:

  * in `ensure_build`: if `now - started_at > ADE_BUILD_TIMEOUT_SECONDS (+ small grace)` ⇒ mark `failed`, remove folder, proceed to build.
  * on startup: perform the same sweep.

### 11) Observability

* [ ] Structured logs with `{ws, cfg, build_id, phase, status, duration_ms, reason?}` for: start build, install engine, install config, verify, activate, prune, failure.
* [ ] Metrics (names illustrative): `ade_build_duration_seconds`, `ade_build_failures_total`, `ade_build_pruned_total`.

### 12) Tests (happy path + failure modes)

* [ ] Unit: builder success & failure cleanup; import check; timeout behavior.
* [ ] Service: dedupe (50 uploads → 1 build), stale‑building healing, pointer flip atomicity, TTL/force triggers, pruning respects job references.
* [ ] API: `GET/PUT/DELETE` semantics; `409` when expected; idempotent `PUT`.
* [ ] Jobs: submitted job records `build_id`; rebuild while another job runs uses old `build_id`; job launches with correct `venv_path`.

### 13) Docs & Finalization

* [ ] Update `docs/developers/02-build-venv.md` to reflect DB‑gated dedupe, timeouts, and self‑healing (keep the rest verbatim).
* [ ] Add a brief runbook note: how to force rebuild, how to interpret “building/failed”, and how pruning works.
* [ ] Ensure CI passes and ship.

---

**Acceptance conditions (quick check):**

* [ ] “50 uploads, 0 builds present” ⇒ exactly **one** build starts; the rest coalesce.
* [ ] Crash mid‑build ⇒ next `ensure_build` heals stale state; no permanent “building” stuck.
* [ ] Rebuild while jobs run ⇒ old jobs finish on old `build_id`; new jobs use new pointer.
* [ ] Delete build refuses when any active job references it; otherwise deletes and next ensure recreates.
* [ ] No runtime metadata files inside venv; DB is source of truth.

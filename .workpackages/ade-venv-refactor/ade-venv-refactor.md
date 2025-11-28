# ADE Virtual Environment Redesign – Work Package (No Backwards Compatibility)
> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---
## 0. Goal

Implement a **new venv system** for ADE that completely replaces the old behavior:

- Venvs **never** live on Azure Files / SMB.
- Builds are **immutable versions** (no in-place rebuilds).
- Multiple containers can run in parallel, each with their own **local cache**.
- DB is the single source of truth for **which build version** is active.
- No feature flags, no shims, no dual code paths – **old behavior is removed**.

All existing venvs and build semantics are invalidated; the new system becomes the **only** behavior.

---

## 1. Problem Summary

The current approach:

- Creates venvs under the data volume (e.g. `<config_root>/.venv`), which in Azure is typically backed by **Azure Files SMB**.
- `python -m venv` fails on SMB due to permission / POSIX limitations.
- Rebuilds are effectively in-place on a single `.venv` folder, which:
  - Risks corrupting environments used by in-flight runs.
  - Is hard to reason about in a multi-container environment.

New design requirements:

- Put venvs on **local container storage** (e.g. `/tmp`), not Azure Files.
- Treat each build as an **immutable, versioned environment** (`build_id`).
- Make containers **lazily hydrate** envs locally from the build spec in DB.
- Simplify the mental model and implementation – no legacy compatibility.

---

## 2. Target Design (Conceptual Overview)

### Core Concepts

1. **Configuration**  
   Defined by `(workspace_id, config_id)`.

2. **Build (Global, Versioned)**  
   - Each build of a configuration gets a unique `build_id`.
   - Each build has a **fingerprint**:
     - Config content digest
     - Engine spec / version
     - Python interpreter / version
     - Other runtime-significant settings
   - A configuration has exactly **one active build** at a time.

3. **Local Environment (Per Container)**  
   - The actual venv directory for `(workspace_id, config_id, build_id)` on a given container.
   - Lives under a local root path (`ADE_VENVS_DIR`), not shared storage.
   - Can be recreated at any time from the build spec in DB.

### Paths & Layout

- New environment variable:

  ```bash
  ADE_VENVS_DIR=/tmp/ade-venvs
````

* Default: `/tmp/ade-venvs` (or equivalent local temp).

* Must be local, writable, POSIX-like storage.

* For `(workspace_id, config_id, build_id)`:

  ```text
  venv_root      = ADE_VENVS_DIR/<workspace_id>/<config_id>/<build_id>/
  venv_path      = venv_root/.venv
  temp_venv_path = venv_root/.venv.tmp
  ```

### Build Semantics

* The **DB decides when a new build is needed** by comparing fingerprints.
* A new build always gets a new `build_id` and new venv directory.
* **Old builds are never mutated in-place.**
* Runs are created with a specific `build_id` and must always use that build.
* Each container **lazily hydrates** the env for a given `build_id` if not present.

---

## 3. Detailed Design & Implementation Tasks

> All tasks assume we are **removing the old venv design outright** and updating code + docs to this new model.

### 3.1. Settings & Configuration

* [x] Add `ADE_VENVS_DIR` handling:

  * [x] Read `ADE_VENVS_DIR` from environment.
  * [x] If not set, default to `/tmp/ade-venvs`.
  * [x] Ensure a `venvs_root` setting is exposed in the settings object.
* [x] Add startup validation:

  * [x] Check `venvs_root` is writable.
  * [x] Log a warning if `venvs_root` looks like a network/SMB mount (best-effort detection).
* [ ] Remove any old venv-related settings (e.g. venv under config root) from code and docs.

### 3.2. Database Schema & Models

* [x] Extend configuration metadata to track the active build:

  * [x] `active_build_id` (string/ULID/UUID)
  * [x] `active_build_fingerprint` (string or JSON)
  * [x] `active_build_status` (`building | active | failed`)
  * [x] `active_build_started_at` (timestamp)
  * [x] `active_build_finished_at` (timestamp, nullable)
  * [x] `active_build_error` (nullable string)

* [x] (Optional but recommended) Add a `builds` table for history:

  * [x] Columns:

    * [x] `build_id` (PK)
    * [x] `workspace_id`
    * [x] `config_id`
    * [x] `fingerprint`
    * [x] `status` (`building | active | failed`)
    * [x] `started_at`, `finished_at`
    * [x] `error` (nullable)
  * [x] Index on `(workspace_id, config_id)`.

* [x] Add DB migrations for new fields / tables.

* [x] Update ORM models and repositories to work with the new schema.

### 3.3. Build Fingerprint

* [x] Define what goes into a fingerprint (e.g.):

  * [x] Canonical config content digest.
  * [x] `ade_engine` dependency spec or resolved version.
  * [x] Python interpreter path + version.
  * [x] Any system-level flags that affect runtime behavior.
* [x] Implement `compute_build_fingerprint(config, engine_spec, python_info) -> str`:

  * [x] Normalize inputs and serialize to JSON or similar.
  * [x] Hash that representation to produce a stable fingerprint string.
* [x] Add unit tests for fingerprint:

  * [x] Same inputs → same fingerprint.
  * [x] Any relevant change → different fingerprint.

### 3.4. Global Build Lifecycle (`ensure_active_build`)

* [x] Implement `ensure_active_build(workspace_id, config_id, force=False) -> build_id`:

  * [x] Load config + current build metadata.

  * [x] Compute fingerprint `F`.

  * [x] If **not** `force` and:

    * [x] `active_build_status == "active"`
    * [x] `active_build_fingerprint == F`
      → **Return** `active_build_id`.

  * [x] Otherwise (no active build, fingerprint changed, or `force=True`):

    * [x] Generate a new `build_id`.
    * [x] Insert/update metadata:

      * [x] `active_build_id = build_id`
      * [x] `active_build_fingerprint = F`
      * [x] `active_build_status = "building"`
      * [x] `active_build_started_at = now`
    * [ ] Persist to DB in a transaction.
    * [ ] Enqueue/dispatch a build job for this `build_id`.

* [x] Add concurrency control:

  * [x] Ensure only one `building` build per `(workspace_id, config_id)` via:

    * [ ] DB constraint or
    * [x] transactional check + update
  * [x] If another request observes `active_build_status="building"`:

    * [x] Either wait for status change or
    * [ ] Return a “build in progress” response and let clients poll.

* [ ] Remove old build-init logic that assumed a single in-place `.venv`.

### 3.5. Builder (Global Build Execution)

* [x] Implement builder logic keyed by `build_id`:

  1. Resolve paths:

     ```text
     venv_root      = ADE_VENVS_DIR/<workspace_id>/<config_id>/<build_id>/
     venv_path      = venv_root/.venv
     temp_venv_path = venv_root/.venv.tmp
     ```

  2. Filesystem operations:

     * [x] `rm -rf temp_venv_path`
     * [x] `mkdir -p venv_root`
     * [x] Run `python -m venv temp_venv_path`.

  3. Install dependencies:

     * [x] Use `temp_venv_path`’s Python to install:

       * [x] `ade_engine` according to `engine_spec`.
       * [x] Configuration package for this `(workspace_id, config_id)`.
     * [x] Write a small **marker file** in the env (e.g. `ade_build.json`) with:

       * [x] `build_id`
       * [x] `fingerprint`
       * [ ] maybe `engine_version`, etc.

 4. Validate:

     * [x] Import `ade_engine`.
     * [x] Import config module.
     * [x] Run minimal smoke checks if desired.

  5. On success:

     * [x] Atomically rename `temp_venv_path` → `venv_path`.
     * [ ] Update DB:

       * [x] `active_build_status = "active"`
       * [x] `active_build_finished_at = now`
       * [x] Clear `active_build_error`.

  6. On failure:

     * [x] `rm -rf temp_venv_path`.
     * [ ] Update DB:

       * [x] `active_build_status = "failed"`
       * [x] `active_build_error` with a concise message.
       * [x] `active_build_finished_at = now`.

* [x] Ensure builder **never** modifies `venv_path` for any other `build_id`.

* [ ] Remove all old builder logic that assumed venvs live under `<config_root>/.venv` or similar.

### 3.6. Run Creation & Build Association

* [ ] Update run creation flow:

  * [ ] When creating a run:

    * [x] Call `ensure_active_build(workspace_id, config_id, force=<from API>)`.
    * [x] If `active_build_status="failed"`, return an error (e.g. “configuration build failed”) and don’t create the run.
    * [x] If successful:

      * [x] Attach `build_id` from `ensure_active_build` to the run record.

* [ ] Update run DB schema:

  * [x] Add `build_id` column to runs table.

* [ ] Ensure all run APIs (list, detail, logs) include `build_id`.
  * [x] Include `build_id` on RunResource responses.
  * [x] Add integration assertions that run detail responses include `build_id`.

### 3.7. Run Execution & Local Hydration

* [x] Implement worker helper: `ensure_local_env(workspace_id, config_id, build_id) -> venv_path`:

  * [x] Compute:

    ```text
    venv_root = ADE_VENVS_DIR/<workspace_id>/<config_id>/<build_id>/
    venv_path = venv_root/.venv
    marker    = venv_root/.venv/ade_build.json
    ```

  * [x] If `venv_path` exists and marker is valid:

    * [x] Return `venv_path`.

  * [x] Otherwise (env missing or invalid):

    * [x] Re-run the **builder logic** for this specific `build_id`, but:

      * [x] Use specs (fingerprint, engine config, etc.) read from DB for that build.
      * [x] Do **not** update `active_build_*` fields in DB.
      * [x] Only create/repair the local env.

* [x] Add per-process (or per-worker) lock keyed by `(workspace_id, config_id, build_id)`:

  * [x] Prevent concurrent hydration attempts for the same build on one container.

* [ ] Integrate into run execution:

  * [x] Before running the job:

    * [x] Load run → get `workspace_id`, `config_id`, `build_id`.
    * [x] Call `ensure_local_env(...)`.
    * [ ] Execute ADE engine with that venv (e.g. using that Python binary or via `subprocess` with appropriate env vars).

### 3.8. Cleanup / GC (Local Only)

* [ ] Implement a lightweight cleanup job per container:

  * [ ] Periodically scan `ADE_VENVS_DIR`.
  * [ ] For each `(workspace_id, config_id)`:

    * [ ] Query DB for `active_build_id`.
    * [ ] For each `build_id` directory under the path:

      * [ ] If `build_id != active_build_id` and `last access or modification > TTL`:

        * [ ] Delete the directory (`rm -rf`).
  * [ ] TTL can be configured via `ADE_VENV_LOCAL_TTL_DAYS` or similar.

* [ ] GC is **best effort**; if it doesn’t run, correctness is unchanged (only disk usage affected).

### 3.9. Removal of Legacy Behavior

* [ ] Delete any code that:

  * [ ] Assumes venv is located under `<config_root>/.venv`.
  * [ ] Rebuilds venv **in-place** for a config without versioning.
  * [ ] Uses any legacy `ADE_*` env vars for venv paths that conflict with `ADE_VENVS_DIR`.
* [ ] Remove / update all old docs that describe:

  * [ ] In-place `.venv` under config.
  * [ ] Azure Files as the location for venvs.
  * [ ] Any previous build semantics that differ from the new versioned design.
  * [ ] (Status: core developer docs updated; sweep ancillary guides/templates for remaining stragglers.)

### 3.10. Observability & Error Reporting

* [ ] Logging improvements:

  * [ ] Always log `workspace_id`, `config_id`, `build_id`, and `run_id` where applicable.
  * [ ] Log build lifecycle:

    * [ ] Build start, success, failure.
  * [ ] Log local hydration:

    * [ ] Hydration start, success, failure per `build_id` on each container.

* [ ] Metrics:

  * [ ] Build durations per config.
  * [ ] Hydration counts and durations.
  * [ ] Build failure rates.
  * [ ] Hydration failure rates.

* [ ] Error messages:

  * [ ] Distinguish clearly:

    * [ ] “Failed to build configuration (global build error).”
    * [ ] “Failed to hydrate local env (local disk, permission, or resource error).”

### 3.11. Testing

* [ ] Unit tests:

  * [ ] `compute_build_fingerprint` correctness.
  * [ ] `ensure_active_build` logic for:

    * [ ] No existing build.
    * [ ] Matching fingerprint.
    * [ ] Changed fingerprint.
    * [ ] `force=True`.
  * [ ] Builder success and failure flows.
  * [ ] `ensure_local_env` hydration behavior.

* [ ] Integration tests:

  * [ ] Full build → run → rebuild cycle:

    * [ ] Verify runs created before rebuild continue to use old `build_id`.
    * [ ] New runs use new `build_id`.
  * [ ] Multi-container scenario:

    * [ ] One container builds globally.
    * [ ] Another container hydrates and executes.
  * [ ] Container restart:

    * [ ] Delete local `ADE_VENVS_DIR`, then execute a run and verify rehydration.
  * [ ] Failure scenarios:

    * [ ] Build errors (bad dependency, insufficient disk).
    * [ ] Hydration errors (no space, permissions).

* [ ] Performance tests:

  * [ ] Measure first run (including build) latency.
  * [ ] Measure subsequent runs (with cached env) latency.

### 3.12. Documentation Updates

* [x] Update ADE developer docs:

  * [x] Explain:

    * [x] Versioned builds (`build_id`).
    * [x] Fingerprints.
    * [x] `ADE_VENVS_DIR` location and requirements.
    * [x] Lazy local hydration.
  * [x] Provide examples of paths and lifecycle.

* [x] Update operations runbooks:

  * [ ] How to:

    * [x] Trigger rebuilds.
    * [x] Diagnose build failures.
    * [x] Diagnose hydration failures.
    * [x] Perform local cleanup if needed.

* [ ] Remove all references to:

  * [ ] Old `.venv` under config directories.
  * [ ] Using Azure Files for venvs.
  * [ ] Legacy build logic or env vars.

---

## 4. Rollout Plan (No Backwards Compatibility)

Because we **do not want backwards compatibility or shims**, rollout is straightforward but requires a clean cutover:

* [ ] Deploy DB migrations to add new build and run fields.
* [ ] Deploy updated application code that implements **only** the new design.
* [ ] Treat all existing configurations as “no active build”:

  * [ ] On first run or explicit build request per config:

    * [ ] `ensure_active_build` creates a new `build_id`.
    * [ ] Builder creates the initial env under `ADE_VENVS_DIR`.
* [ ] Optionally:

  * [ ] Delete legacy venv directories under data volumes as part of operational cleanup.
* [ ] Verify:

  * [ ] Builds succeed for representative configs.
  * [ ] Runs execute correctly on one and multiple containers.
  * [ ] Local hydration works after container restarts.

---

## 5. Acceptance Criteria

* [ ] All venvs are created under `ADE_VENVS_DIR` (default `/tmp/ade-venvs`) on local storage.
* [ ] No code path attempts to create or use venvs on Azure Files / SMB.
* [ ] Builds are **immutable**, identified by `build_id`; no in-place rebuilds occur.
* [ ] Runs are tied to a specific `build_id` and keep working even after newer builds are created.
* [ ] Multiple containers can:

  * [ ] Use the same `build_id` from DB.
  * [ ] Hydrate local envs independently on their own disks.
* [ ] Container restarts do not break the system; envs are rehydrated as needed.
* [ ] All documentation aligns with this new design; no references to the old behavior remain.

> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Add a configurable venv retention period (env var, default 30 days) to settings
* [x] Track `last_used_at` and a build digest on `configurations`
* [x] Implement “dirty” detection for configurations (digest/venv/status) and auto-rebuild on run start
* [x] Add a placeholder function for future venv/document cleanup logic
* [x] Wire auto-rebuild into the existing build/run orchestration
* [ ] Update docs and tests to cover auto-build-on-run behavior and the retention placeholder

---

# Auto-Rebuild & TTL Venv Cleanup (with cleanup placeholder)

## 1. Objective

**Goal:**
Make configuration builds effectively **invisible** to users by:

* Automatically rebuilding the config’s venv whenever a run starts and the config is **dirty** (source files changed or venv missing).
* Preparing for cleanup of unused venvs (and eventually documents) via a **retention setting**, with the actual cleanup mechanism implemented later.

You will:

* Add **retention settings** and tracking fields to configurations.
* Implement **dirty detection** and **auto-build** as part of the run pipeline.
* Add a placeholder cleanup function to be filled in later (no operational scanning yet).
* Ensure runs always see a **ready** environment without the user needing to manually “build”.

The result should:

* Keep builds **self-healing** and—eventually—**self-cleaning**.
* Require no conceptual understanding of “builds” from the end user.
* Provide a place to hook in future cleanup for unused venvs and uploaded documents.

---

## 2. Context (What you are starting from)

* **Storage layout:**
  One venv per configuration, stored under the config package:

  ```
  ./data/workspaces/<workspace_id>/config_packages/<configuration_id>/.venv/
  ```

* **Schema (current design direction):**

  * `configurations` holds config metadata & build state.
  * `configuration_builds` has been removed.
  * `builds` is the job table for build attempts.

* **Runtime behavior:**

  * Venv is created by the build pipeline at `<config_root>/.venv`.
  * Runs use that venv directly; there is no environment-level build ID.

* **New requirement:**

  * Auto-rebuild when dirty.
  * Add retention and timestamps to prepare for future cleanup, but **do not implement active scanning yet**.

---

## 3. Target architecture / structure (ideal)

### 3.1 Settings

Extend `Settings` with a **build/venv retention** concept:

```python
build_retention: timedelta | None = Field(default=timedelta(days=30))
```

ENV form:

```
ADE_BUILD_RETENTION=30d
```

Semantics:

* `None` → retention disabled.
* `timedelta` → retained for that duration; cleanup handled later via a placeholder.

### 3.2 Config state tracking

`configurations` should track:

* `content_digest` — digest of config source tree at last build
* `build_status` — `'idle' | 'building' | 'ready' | 'failed'`
* `last_build_finished_at` — timestamp
* `last_used_at` — timestamp updated on runs
* `build_error` — optional text

### 3.3 Dirty detection

A config is **dirty** if:

* `.venv` does not exist, OR
* `build_status != 'ready'`, OR
* Source digest ≠ stored `content_digest`

### 3.4 Cleanup placeholder

We add:

```python
def mark_stale_envs_for_cleanup(...):
    """
    Placeholder for future cleanup logic.
    Will eventually mark venvs (and documents) unused beyond retention
    for deletion by a cleanup scheduler.
    """
    pass
```

No actual deletions occur yet.

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Invisible builds:** Users only see “Run”; building happens automatically if needed.
* **Future-proof cleanup:** Retention settings + timestamps exist today; actual cleanup comes later.
* **Deterministic behavior:** Dirty detection should be clear and repeatable.

### 4.2 Key components / modules

* Settings (`build_retention`)
* Config digest computation
* `ensure_config_env_ready()` for auto-rebuild
* Cleanup placeholder for future integration
* Build pipeline (existing)
* Run pipeline (modified to call auto-rebuild)

### 4.3 Key flows / pipelines

#### Flow 1 — Run start (auto-rebuild)

1. User requests run.

2. Backend loads config row.

3. Calls:

   ```python
   ensure_config_env_ready(settings, config)
   ```

4. Inside `ensure_config_env_ready`:

   * Compute `config_root` and `venv_dir = config_root / ".venv"`
   * Dirty detection:

     * venv missing → **dirty**
     * `build_status != 'ready'` → **dirty**
     * digest mismatch → **dirty**
   * If dirty → rebuild inline:

     * Delete existing `.venv`
     * Create new venv
     * Install `ade_engine` + config
     * Compute & store new digest
     * Set `build_status='ready'`, timestamps updated
   * Return `venv_dir`

5. Run worker uses `venv_dir/bin/python`.

6. On success → `config.last_used_at = now()`.

#### Flow 2 — Venv/document cleanup placeholder

* Eventually want:

  * TTL-based cleanup of unused venvs and old uploaded documents.
* For now:

  * A stub function records the **intended cleanup logic** but performs **no filesystem changes**.

---

## 4.4 Open questions / decisions

* Digest or mtime for dirty detection?
  **Decision:** digest-based for correctness.
* Should rebuild be synchronous or queued?
  **Decision:** synchronous during run startup.
* Should we lock per-configuration?
  **Decision:** yes, to avoid concurrent rebuild races.
* Cleanup mechanism?
  **Decision:** **placeholder for now**, real cleanup to be implemented later.

---

## 5. Implementation & notes for agents

### 5.1 Settings

Add to `Settings`:

```python
build_retention: timedelta | None = Field(default=timedelta(days=30))
```

Document in `.env.example`:

```
# How long to retain unused configuration environments (.venv)
# Accept 'Xs', '5m', '12h', '30d' etc.
ADE_BUILD_RETENTION=30d
```

### 5.2 Config digest helper

Implement:

```python
def compute_config_digest(config_root: Path) -> str:
    # Walk config_root, excluding ".venv", hash file contents
```

Use on build completion + run startup.

### 5.3 ensure_config_env_ready

Implement:

```python
def ensure_config_env_ready(settings, config):
    # compute paths
    # detect dirty
    # if dirty → rebuild now
    # return venv_dir
```

Rebuild logic:

* Delete `.venv/`
* `python -m venv`
* Install engine + config
* Compute digest
* Update DB fields

### 5.4 Cleanup placeholder

Add:

```python
def mark_stale_envs_for_cleanup(settings, now):
    """
    Placeholder. Later we will:
      - find stale venvs/documents (older than build_retention)
      - delete them
      - update DB
    For now: no-op except maybe log/collect candidates.
    """
    return []
```

### 5.5 Tests & docs

* Tests for auto-build-on-run:

  * If config is clean → no rebuild
  * If dirty (modify a file) → rebuild
  * If venv missing → rebuild
* Tests for retention placeholder:

  * No deletions, but returns expected candidates
* Docs update:

  * Explain dirty detection & auto-build
  * Explain retention concept + placeholder for cleanup

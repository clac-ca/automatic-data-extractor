# Work Package: **Config Packages — Unified Build & Run** (WP‑0013)

**Owner:** jkropp (proposed)
**Status:** Active (ready to implement)
**Reviewed:** 2025‑11‑04

> **Problem to solve:** Draft configs need to be **testable** without special paths, and activation should not be the only moment we build a venv.
> **Solution:** Use **one simple, consistent pipeline** for *every* run—draft or active:
>
> **Prepare (build venv) → Run job in that venv → (optional) Activate.**
>
> Build artifacts (logs, packages, interpreter path) live **inside the venv**, not in the configs folder. The configs folder remains **source-only**.

---

## 0) TL;DR — what changes

* **Single pipeline for all runs:**
  Jobs (test or production) always execute in a **per‑version venv** that contains a copy of the package at `venv/.ade/config/`.
* **Prepare once, run many:**
  A new **Prepare** step creates the venv, installs `requirements.txt`, runs the prepare/activate hooks, and snapshots the environment.
  Activation simply marks the prepared version **active** (no builds during activate).
* **Store activation/prepare artifacts in venv:**
  `venvs/<config_version_id>/.ade/prepare/*` (logs, `packages.txt`, status.json, hooks.json).
* **Configs folder is read-only source:**
  `configs/<workspace_id>/<config_version_id>/` holds only the package files (manifest + scripts + optional requirements.txt).
* **Drafts are testable:**
  If a draft isn’t prepared, the job path **auto‑prepares** on first test run or you can call **Prepare** explicitly.
* **Clone/Rollback:**
  New version = **clone** of an existing version → edit as draft → **prepare** → (optional) **activate**.
  Rollback = clone prior version + activate.

---

## 1) States & lifecycle

**Version status (DB):** `draft | active | archived` (unchanged, simple)

**Preparation status (DB):** `none | preparing | prepared | failed`
*(new fields; keeps the main status simple while tracking readiness)*

**Lifecycle**

1. **Create draft** (from template / clone / import).
2. **Prepare** draft:

   * build venv at `venvs/<version_id>/`
   * copy package into `venv/.ade/config/`
   * `pip install -r requirements.txt` (if present)
   * `pip freeze → .ade/prepare/packages.txt`
   * run **prepare hooks** (alias of `on_activate` for BC)
   * write `.ade/prepare/{install.log, hooks.json, status.json}`
   * set `prepare_status=prepared`, `prepared_at=…`, record `venv_path` & `python_executable`
3. **Test** draft: submit jobs with `config_version_id` (or use “test” flag).
   (If not prepared, the job **auto‑prepares** once.)
4. **Activate**: flip **only** the status in DB (enforce single active). No builds.
5. **Rollback**: clone old version → prepare if needed → activate.

---

## 2) Storage layout

```
data/
  configs/
    <workspace_id>/
      <config_version_id>/        # source (read-only)
        manifest.json
        columns/
        hooks/
        row_types/
        requirements.txt?
  venvs/
    <config_version_id>/
      bin/python*                # venv interpreter used by jobs
      ...
      .ade/
        config/                  # copy of the version package used at runtime
          manifest.json
          columns/
          hooks/
          row_types/
          requirements.txt?
        prepare/
          status.json            # {"state":"prepared"|"failed", ...}
          install.log
          packages.txt
          hooks.json
          metadata.json          # python_executable, pip version, etc.
```

* **All** build/prepare artifacts live under `venvs/<version_id>/.ade/prepare/`.
* **Jobs** read `ADE_CONFIG_DIR=<venv>/.ade/config`.
* **Orchestrator** always uses `<venv>/bin/python` for the worker.

---

## 3) API surface

### Create Draft (template first, import later)

`POST /api/v1/workspaces/{ws}/configs/drafts`

* **Auth:** `Workspace.Configs.ReadWrite`, **CSRF** required
* **Body (template mode):**

  ```json
  { "mode": "template", "title": "Member Intake", "template_version_id": null }
  ```
* **Response:** config + new draft version (status `draft`, `prepare_status: "none"`)

> *Import mode (“later”):* same endpoint, `mode=import` with `multipart` file `package.zip`. Kept out-of-scope for Phase 1 but design is ready.

### Prepare Version (build venv + hooks)

`POST /api/v1/workspaces/{ws}/configs/versions/{version_id}/prepare`

* Builds venv if missing; installs deps; `pip freeze`; runs prepare hooks.
* **Response:**

  ```json
  {
    "version_id":"cfgv_…",
    "prepare_status":"prepared",
    "venv_path":"/.../venvs/cfgv_…",
    "python_executable":"/.../venvs/cfgv_…/bin/python",
    "packages_uri":".../.ade/prepare/packages.txt",
    "install_log_uri":".../.ade/prepare/install.log",
    "hooks_uri":".../.ade/prepare/hooks.json"
  }
  ```
* **Errors:** `400 dependency_install_failed | prepare_hook_failed`, `404 version_not_found`

### Activate Version (flip only)

`POST /api/v1/workspaces/{ws}/configs/versions/{version_id}/activate`

* Ensures `prepare_status=prepared` (if not: **auto‑prepare**, unless `?no_auto_prepare=true`).
* Flips single active invariant.
* **Response:** active version metadata; previous active archived.

### Clone Version (new version / rollback base)

`POST /api/v1/workspaces/{ws}/configs/versions/{version_id}/clone`

* **Body:**

  ```json
  { "activate": false, "label":"v3 (hotfix)", "notes":"rollback from v2" }
  ```
* Copies source package dir to new `v####` under same config; recompute hashes.
* If `activate=true`: prepare (if needed) then activate (rollback).

### Jobs — test vs production

* `POST /api/v1/workspaces/{ws}/jobs` (existing)

  * **Change:** `config_version_id` becomes **optional** (defaults to active).
  * **Test runs:** pass `mode:"test"` (or `test:true`) to tag the job; jobs are otherwise identical.
  * **Behavior:** if the referenced version is **not prepared**, the service **ensures prepare** before running.

### Active lookup (nice‑to‑have)

`GET /api/v1/workspaces/{ws}/configs/active` → active config + version

### Deprecation / consolidation

* Existing `POST /workspaces/{ws}/configs` (upload) **delegates** to `POST /configs/drafts` (import mode) and returns a **Deprecation** warning + `Link` to the new endpoint.

---

## 4) Data model & migration

**Table: `config_versions`** *(add fields; keep existing status enum)*

* `status` **ENUM**(`draft|active|archived`) — **already planned**
* `prepare_status` **ENUM**(`none|preparing|prepared|failed`) — **new**
* `prepared_at` **timestamptz** — **new**
* `venv_path` **varchar(512)** — **new**
* `python_executable` **varchar(512)** — **new**
* `prepare_packages_uri` **varchar(512)** — **new**
* `prepare_install_log_uri` **varchar(512)** — **new**
* `prepare_hooks_uri` **varchar(512)** — **new**

**Migration `0003_config_preparation_fields.py`:**

* Add above columns with sensible defaults.
* Backfill: existing active → `prepare_status="prepared"` **only if** venv exists; else `"none"`.
* Remove `workspace_config_states` usage in services (keep table if you want as a denorm cache or drop later).

**Invariant:** 1 active per `config_id` (service‑enforced; DB unique partial index optional later).

---

## 5) Orchestrator & runtime

* **Always run in venv**: Worker process is launched with `<venv>/bin/python`.
* **Ensure prepare**:

  * Before a job runs, the service calls `EnsurePrepared(version_id)`; if `none/failed`, it executes the prepare pipeline (with network allowed).
  * Only after successful prepare, the worker launches (with network **off** by default).
* **No `vendor/` per job**: remove PYTHONPATH vendor injection once prepare path is live.
* **Record provenance**: put `python_executable` and `venv_path` into `run-request.json`.

---

## 6) Network policy (simple & consistent)

* **Prepare**: outbound network **allowed** (to install deps, download models, etc.).
* **Run**: network **blocked by default** unless manifest `engine.defaults.runtime_network_access: true`.
* **Backward compat**: accept legacy `allow_net` → map to `runtime_network_access` with a deprecation diagnostic.

---

## 7) Template & cloning

* **Default template** lives in-repo: `backend/app/features/configs/templates/default/` (manifest + empty columns/hooks + optional commented `requirements.txt`).
* **Clone** uses the stored **source package** (configs/…), not the venv; never copies prepare artifacts.
* If an ancient version lacks a full package, fallback to `venv/.ade/config/` as a last resort (logged).

---

## 8) Housekeeping & space efficiency

* **Idempotent prepare**: re‑running prepare is a no‑op if `prepared` and hashes unchanged.
* **GC** (later): `venvs` for archived versions older than N days may be pruned via an admin task.
* **(Optional later)**: deduplicate venvs by digest of `requirements.txt` + Python version (out of scope now).

---

## 9) Security & permissions

* All config‑mutating routes require `Workspace.Configs.ReadWrite` + CSRF.
* Prepare runs in a constrained subprocess; capture full logs.
* ZIP import validator (when enabled) must enforce allowlist, size caps, and reject hidden/symlink/binary entries.

---

## 10) Rollout plan (minimal risk)

1. **Phase 1 — Template drafts + Prepare + Test**

   * Create draft from template
   * Implement **Prepare** (build venv, hooks, metadata)
   * Orchestrator **requires venv** (auto‑prepare if needed)
   * Jobs support `mode:"test"` & optional `config_version_id`
2. **Phase 2 — Activate & Clone/Rollback**

   * Flip active (no builds)
   * Add `clone` (with optional `activate=true`)
   * Enforce single active invariant
3. **Phase 3 — Import & Cleanup**

   * Draft import (zip) + validator
   * Deprecate legacy upload route
   * Docs & GC hooks

---

## 11) Implementation checklist (agent‑tickable)

### A) Template → Draft (Phase 1)

* [ ] Add `backend/app/features/configs/templates/default/{manifest.json, columns/__init__.py, hooks/__init__.py, requirements.txt?}`
* [ ] `TemplateLoader.load("default") -> TemplatePackage`
* [ ] `ConfigsService.create_draft_from_template(workspace_id, template_version_id?, title?, config_id?)`
* [ ] `POST /configs/drafts` (template mode) + tests (happy path, rename handling, WS mismatch)

### B) Prepare pipeline (Phase 1)

* [ ] `activation_env.py` → **rename/extend** to `prepare_env.py` with:

  * [ ] `ensure_prepared(version_id)` (idempotent)
  * [ ] `create_venv(version_id) -> Path`
  * [ ] `install_requirements(venv_path, requirements_path) -> install.log`
  * [ ] `freeze_packages(venv_path) -> packages.txt`
  * [ ] `run_prepare_hooks(venv_path/.ade/config) -> hooks.json`
  * [ ] write `.ade/prepare/status.json` + `metadata.json`
* [ ] Add DB fields (`prepare_status`, `prepared_at`, `venv_path`, etc.)
* [ ] `ConfigsService.prepare_version(version_id)` sets DB fields + returns pointers
* [ ] Orchestrator: **always** pick `python_executable` from DB; if missing → call `ensure_prepared(version_id)`
* [ ] Tests: prepare success, prepare idempotent, failure logs & `prepare_status=failed`

### C) Jobs (Phase 1)

* [ ] `JobSubmitRequest` → `config_version_id` **optional**
* [ ] JobsService: resolve active by default; if none and no explicit → `400 {code:"no_active_config"}`
* [ ] If version not prepared: call `ensure_prepared` before enqueuing the job (or lazily in worker before launch)
* [ ] `mode:"test"` supported (tag job kind; same outputs)
* [ ] Tests: default active, no active → error, draft test with auto‑prepare

### D) Activate (Phase 2)

* [ ] `POST /configs/versions/{id}/activate`:

  * [ ] ensure prepared (unless `no_auto_prepare`)
  * [ ] flip single active (transaction)
* [ ] Drop/replace usage of `workspace_config_states`
* [ ] Tests: activate prepared draft; activate auto‑prepares; single‑active enforced

### E) Clone & Rollback (Phase 2)

* [ ] `POST /configs/versions/{id}/clone` (+ optional `activate=true`)
* [ ] Service: copy source package dir → new version dir; recompute hashes; validate; create draft
* [ ] Rollback path: clone → prepare (if needed) → activate
* [ ] Tests: clone active→draft; clone archived→draft; clone+activate

### F) Import (Phase 3)

* [ ] Extend `POST /configs/drafts` with `mode=import` (multipart)
* [ ] ZIP validator: allowlist, size caps, no hidden/symlink/binary/`..`
* [ ] Tests: happy import; unsafe entry; oversize
* [ ] Route deprecation: legacy upload delegates + `Deprecation` header

### G) Docs (Phase 1→3)

* [ ] Update developer docs:

  * [ ] “Build once, run many” (Prepare → Run → Activate)
  * [ ] Storage layout (configs vs venvs)
  * [ ] Test drafts (auto‑prepare)
  * [ ] Network policy (prepare vs run)
  * [ ] Clone/Rollback
* [ ] Example cURL for prepare, test run, activate, clone

---

## 12) Acceptance criteria

* Draft from template → **Prepare** builds venv & artifacts in `venv/.ade/prepare/`
* Test job against draft **auto‑prepares** if needed; job runs in the venv; provenance recorded
* Activate **does not build**; it flips active and archives previous active atomically
* Clone creates a new draft from any version; optional `activate=true` performs rollback in a single call
* No build artifacts in `configs/`; all under `venvs/`
* Network is **allowed** during prepare, **blocked by default** during run (unless opted in)
* Legacy upload route delegates to drafts when import is shipped

---

## 13) Risks & mitigations

* **Long prepare times** → add logs, timeouts, retries; keep idempotent; expose progress via `status.json`.
* **Multiple actives** → flip in a transaction; add service guards & tests.
* **Space growth** → prepare is idempotent; later GC for old archived venvs.
* **Inconsistent envs** → worker must refuse to run without `prepared` status; provenance recorded per job.

---

## 14) Telemetry (nice to have)

* Counts & durations: prepare runs, pip failures, hook failures
* Job mix: test vs prod, runs per version
* Venv disk usage over time

---

## 15) Design notes (compatibility & simplicity)

* Keep **status enum** (`draft|active|archived`) stable; add **preparation fields** rather than new statuses → **simpler DB**.
* Treat `on_activate` as **prepare hook** now; keep the name for backward compatibility but document the timing change.
* Start with **template‑only** drafts (Phase 1). Import arrives later without touching Prepare/Run semantics.
* Orchestrator uses **one code path** for every job: **ensure prepared → run in venv**. No special‑case for drafts or actives.

---

### Default template (starter)

`backend/app/features/configs/templates/default/manifest.json` (minimal):

```json
{
  "config_script_api_version": "1",
  "info": { "schema": "ade.manifest/v1.0", "title": "New Config", "version": "0.1.0" },
  "engine": {
    "defaults": {
      "timeout_ms": 60000,
      "memory_mb": 512,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.0
    },
    "writer": { "mode": "row_streaming", "append_unmapped_columns": true, "unmapped_prefix": "raw_", "output_sheet": "Normalized" }
  },
  "env": {},
  "hooks": {
    "on_activate": [],               // treated as "prepare hook"
    "on_job_start": [],
    "after_mapping": [],
    "after_transform": [],
    "after_validate": [],
    "on_job_end": []
  },
  "columns": { "order": [], "meta": {} }
}
```

`columns/__init__.py`:

```python
# placeholder
```

`hooks/__init__.py`:

```python
# placeholder
```

`requirements.txt` (optional):

```
# pandas==2.2.2
# pyarrow==17.0.0
```

---

**That’s it:** build once into a venv, run every job in that venv, flip a pointer to activate. Simple, consistent, testable, and storage‑friendly.

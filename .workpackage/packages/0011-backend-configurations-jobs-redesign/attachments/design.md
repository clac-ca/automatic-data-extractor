# Backend Config Engine v0.5 — Backend Design

## 0) Executive summary

A **config** is a folder at `data/configs/<config_id>/` containing a `manifest.json`, optional hook scripts, and one Python **column module** per canonical output column. A workspace may own many configs, but only **one is `active`** at any time; others are `inactive` or `archived`. The database holds **metadata only** (ids, titles, status, timestamps, active pointer). The filesystem holds **behavior** (manifest + scripts). Jobs execute the active config in a **sandboxed Python subprocess** pipeline: hooks → **detect** (each column module runs its `detect_*` functions over every raw column) → **assign** (greedy best match) → **transform** (normalize values) → post‑hooks. Export/import is just **zip/unzip** of the folder.

**v0.5 vs v0.4 highlights**

* Script API clarified: **explicit kwargs** and **multiple `detect_*` + single `transform`** per column module.
* Status model fixed to **`active | inactive | archived`** (only 1 active per workspace).
* API routes standardized (RESTful; no colon verbs).
* Validation strengthened (module introspection, quick dry‑run, secret checks).
* Simpler storage: **single folder per config**; immutability enforced by API (no draft/publish directories).

---

## 1) Core concepts

### 1.1 Minimal data model (SQLite)

* `workspaces(id, name, active_config_id NULL FK → configs.id)`
* `configs(id PK, workspace_id FK, status ENUM('active','inactive','archived') DEFAULT 'inactive', title, note, version DEFAULT '0.0.1', base_config_id NULL, package_sha256 NULL, size_bytes NULL, created_by NULL, created_at, updated_at, archived_at NULL)`

**Invariant:** For each workspace, at most **one** config has `status='active'`, and `workspaces.active_config_id` points to it.

**ASCII view**

```
┌─────────────── workspaces ───────────────┐
│ id (PK) │ name │ active_config_id (FK)   │
└──────────────────────────────────────────┘

┌────────────────────────── configs ──────────────────────────┐
│ id (PK) │ workspace_id (FK) │ status │ title │ version ... │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Filesystem as source of truth

```
data/configs/<config_id>/
  manifest.json
  on_activate.py?          # optional
  on_job_start.py?         # optional
  on_after_extract.py?     # optional
  on_job_end.py?           # optional
  columns/
    <canonical_key>.py     # one module per output column
  README.md?               # optional
```

**Manifest (v0.5)**
Increment schema field to signal the clarified script API: `"info.schema": "ade.manifest/v0.5"`.

```json
{
  "info": { "schema": "ade.manifest/v0.5", "title": "Starter", "version": "0.0.1" },
  "env": { "LOCALE": "en-CA", "DEFAULT_CURRENCY": "CAD" },
  "secrets": {
    "OPENAI_API_KEY": { "alg": "AES-256-GCM", "kdf": "HKDF-SHA256", "key_id": "default",
                        "nonce": "...", "salt": "...", "ciphertext": "...", "created_at": "..." }
  },
  "engine": { "defaults": { "timeout_ms": 1000, "memory_mb": 512, "allow_net": false } },
  "hooks": {
    "on_activate":      [ { "script": "on_activate.py",   "limits": { "timeout_ms": 3000 } } ],
    "on_job_start":     [ { "script": "on_job_start.py" } ],
    "on_after_extract": [ ],
    "on_job_end":       [ ]
  },
  "columns": {
    "order": ["member_id", "invoice_total"],
    "meta": {
      "member_id":     { "label": "Member ID",     "required": true,  "enabled": true, "script": "columns/member_id.py" },
      "invoice_total": { "label": "Invoice Total", "required": false, "enabled": true, "script": "columns/invoice_total.py" }
    }
  }
}
```

---

## 2) Script APIs (explicit, discoverable)

### 2.1 Hooks (keyword‑only `run(...)`)

```python
# on_activate.py
def run(*, workspace_id: str, config_id: str, env: dict, paths: dict) -> dict | None: ...
# on_job_start.py
def run(*, workspace_id: str, config_id: str, job_id: str, env: dict, paths: dict, inputs: dict) -> dict:
    # Return {"jobContext": {...}}
# on_after_extract.py
def run(*, workspace_id: str, config_id: str, job_id: str, env: dict, paths: dict, mapping: dict, warnings: list[str]) -> dict | None: ...
# on_job_end.py
def run(*, workspace_id: str, config_id: str, job_id: str, env: dict, paths: dict, success: bool, error: str | None) -> dict | None: ...
```

`paths = {"config","resources","cache","job","job_input"}` (all absolute).

### 2.2 Column modules (many `detect_*`, one `transform`)

```python
# Detectors: run on every raw input column
def detect_<name>(*,
    header: str, values: list, column_index: int,
    table: dict, job_context: dict, env: dict
) -> dict:
    # Return {"scores": {"self": +float, "<other_key>": +/-float}}

# Transformer: run once on the assigned raw column
def transform(*,
    header: str, values: list, column_index: int,
    table: dict, job_context: dict, env: dict
) -> dict:
    # Return {"values": [...], "warnings": [str]?}  (len(values) == table["n_rows"])
```

**Notes**

* `table` is a light view: `{"id","name","n_rows","n_cols","headers":[...],"samples":[...]}`.
* Full input lives at `paths["job_input"]` (JSON); modules may read it if needed.
* Server **clamps** each score contribution to `[-5.0, +5.0]`.

---

## 3) Pipeline (server responsibilities)

1. **Extract input** → write `JOB_INPUT.json` under `paths["job"]`.
2. **on_job_start** → build/merge `jobContext`.
3. **Detect** → for each canonical key `k` (each column module) and each raw column `r`:

   * call all `detect_*` functions; `score[k][r] += sum(deltas)`.
4. **Assign** (greedy v0.5):

   * candidates = all `(k, r, score)` with `score > 0`.
   * sort desc; pick if `k` and `r` unassigned.
5. **Transform** → for each assigned `(k, r)`, call `transform(...)`; collect `values` (must match `n_rows`).
6. **on_after_extract** → pass mapping + warnings.
7. **on_job_end** → `success` or `error` explanation.

**Pseudocode**

```python
job_ctx = run_on_job_start()
score = defaultdict(lambda: defaultdict(float))
for k in canonical_keys:
  mod = import_module(script_for(k))
  detects = [f for name,f in functions(mod) if name.startswith("detect_")]
  for r in raw_columns:
    for det in detects:
      delta = det(header=r.header, values=r.values, column_index=r.idx,
                  table=table_light, job_context=job_ctx, env=env)
      for key, val in clamp(delta["scores"], -5.0, 5.0).items():
        score[key][r.id] += val

assignments = greedy(score)  # only positives; one-to-one
for k, r in assignments:
  out = mod.transform(header=r.header, values=r.values, column_index=r.idx,
                      table=table_light, job_context=job_ctx, env=env)
  assert len(out["values"]) == table_light["n_rows"]
```

---

## 4) Runtime & isolation (sandbox)

* **Process:** `python -I -B` per call (simple & safe).
* **Limits:** rlimits for CPU, RSS, and file size; **timeouts** from per‑entry limits or engine defaults.
* **Network:** off by default (`engine.defaults.allow_net=false`).
* **Working dir:** `data/configs/<config_id>/` (prepend `resources/vendor` to `sys.path` if present).
* **Environment in child:**

  1. baseline (`PATH`, `LC_ALL=C`, `PYTHONIOENCODING=utf-8`)
  2. `manifest.env`
  3. **decrypted** `manifest.secrets` (plaintext exists **only** in the child)
  4. ADE vars:

     ```
     ADE_WORKSPACE_ID, ADE_CONFIG_ID, ADE_JOB_ID,
     ADE_EVENT, ADE_COLUMN_KEY?,
     ADE_PATH_CONFIG, ADE_PATH_RESOURCES, ADE_PATH_CACHE, ADE_PATH_JOB, ADE_PATH_JOB_INPUT
     ```
* **I/O:** kwargs as JSON on stdin; JSON on stdout. Redact secret values in logs.

---

## 5) Validation rules

* **Structure:** only allowed roots (manifest, hook files, `columns/`, `resources/`, optional docs).
* **Manifest:** schema `"ade.manifest/v0.5"`; unique `columns.order`; every key has `meta[key].script` that exists; hooks point to existing files.
* **Columns:** each module has ≥1 `detect_*` and a callable `transform`.
  Quick dry‑run: tiny 2–3 row inputs, timeouts enforced, return shapes checked.
* **Hooks:** if present, module exports callable `run`.
* **Secrets:** ciphertext only in manifest; bundle/file endpoints must **not** accept plaintext.
* **Limits:** `limits.timeout_ms` within `[1, 300_000]`.
* **Integrity:** compute canonical ZIP + `package_sha256` (sorted paths, normalized metadata) for auditing.

**Response shape**

```json
{ "ok": true, "diagnostics": [ { "path": "columns/member_id.py", "level": "warning", "code": "LINT001", "message": "..." } ] }
```

---

## 6) API (FastAPI; RESTful; backend‑only)

**Base prefix:** `/api/v1/workspaces/{workspace_id}/configs`

### 6.1 CRUD & lifecycle

* `GET    /` — list configs (`?status=active|inactive|archived|all`, default active+inactive)
* `POST   /` — create **inactive** config from template or clone (`{title?, note?, from_config_id?}`) → `{id}`
* `GET    /{config_id}` — metadata
* `PATCH  /{config_id}` — update `{title|note|version}`; change `status` to `archived|inactive` (guard `active`)
* `DELETE /{config_id}` — delete if `inactive|archived`
* `GET    /active` — current active config (404 if none)
* `POST   /{config_id}/activate` — atomically switch active; run `on_activate` (rollback on error)

### 6.2 Files & manifest

* `GET  /{config_id}/manifest`
* `PUT  /{config_id}/manifest` — validate on write; reject plaintext secrets
* `GET  /{config_id}/files`
* `GET  /{config_id}/files/{path:path}`
* `PUT  /{config_id}/files/{path:path}` — text files; atomic write (temp + rename)
* `DELETE /{config_id}/files/{path:path}`
* `POST /{config_id}/rename` — atomic column key/file rename

### 6.3 Import / export / validate / clone

* `POST /import` — multipart `.zip` → new **inactive** config
* `GET  /{config_id}/export` — stream zip
* `POST /{config_id}/validate` — run validation rules and quick dry‑run
* `POST /{config_id}/clone` — deep copy folder → new **inactive** config

### 6.4 Secrets (plaintext never returned)

* `GET    /{config_id}/secrets` — list `{name, key_id, created_at}[]`
* `POST   /{config_id}/secrets` — `{name, value}`; server encrypts into manifest
* `DELETE /{config_id}/secrets/{name}` — remove entry

**Statuses:** only `inactive` is editable; `active` and `archived` are read‑only. Service enforces “one active per workspace”.

---

## 7) Code structure (backend package)

```
backend/app/features/configs/
  models.py        # SQLAlchemy Config + enum
  schemas.py       # Pydantic: ConfigRecord, Manifest(v0.5), ValidationIssue, FileItem
  exceptions.py    # ConfigNotFound, ActivationFailed, ManifestInvalid, Conflict, ...
  dependencies.py  # DB session, auth/workspace guard, storage root
  repository.py    # DB ops only
  files.py         # manifest load/save, list, read/write/delete, zip import/export, safe rename
  sandbox.py       # subprocess runner for hooks & column modules; env injection
  validation.py    # structure, manifest, module introspection, dry-run
  service.py       # orchestrates DB+FS; CRUD, activate, clone, import/export, validate, secrets
  router.py        # FastAPI routes -> service; exception mapping
  templates/default/
    manifest.json
    on_job_start.py
    columns/member_id.py
    columns/invoice_total.py
    README.md
```

**Key service functions**

```python
create_config(workspace_id, title?, from_config_id?) -> ConfigRecord
activate_config(workspace_id, config_id) -> ConfigRecord
archive_config(config_id) / unarchive_config(config_id)
clone_config(config_id) -> new ConfigRecord
import_config(workspace_id, zip_bytes) -> ConfigRecord
export_config(config_id) -> zip_bytes

get_manifest(config_id) -> Manifest
put_manifest(config_id, manifest: Manifest) -> Manifest

list_files(config_id) -> list[FileItem]
read_file(config_id, rel_path) -> str
write_file(config_id, rel_path, content: str) -> None
delete_file(config_id, rel_path) -> None
rename_column(config_id, from_key, to_key) -> Manifest

validate_config(config_id) -> list[ValidationIssue]
```

---

## 8) Security, observability, failure modes

* **Secrets:** AES‑256‑GCM (`ADE_SECRET_KEY`: Base64 32‑byte) with HKDF salt; plaintext exists only in child env. Logs redact known secret values.
* **Sandbox:** network disabled by default; strict timeouts; cap CPU/RSS; cwd isolated; allowlist env.
* **Auditing:** store `package_sha256` (canonical zip) in DB for integrity.
* **Logging:** structured JSON per script execution (`event`, `module`, `elapsed_ms`, `timeout`, `exit_code`, `truncated_output`, `warnings_count`).
* **Failure modes:**

  * Activation hook fails → revert active pointer and status, return 409.
  * Detector returns wrong shape → validation error.
  * Transform returns wrong length → runtime error; mark job failed; still run `on_job_end`.
  * Manifest references missing file → validation error / 422 on PUT.

---

## 9) Settings (.env)

```
ADE_STORAGE_CONFIGS_DIR=data/configs
ADE_SECRET_KEY=  # Base64-encoded 32 bytes
```

*(Keep other app settings as-is; no object storage in v0.5.)*

---

## 10) Migration & rollout

1. **Archive** legacy config feature under `_legacy_configurations/`.
2. **Add** `configs` table + `workspaces.active_config_id`; **drop** legacy config/version/script tables.
3. **Introduce** the new router under `/api/v1/workspaces/{workspace_id}/configs`.
4. **Jobs** resolve the active config via `workspaces.active_config_id`.
5. **Seed** a starter config by copying `templates/default/` when creating a new config.

---

## 11) Example (for instant clarity)

**DB rows**

```
workspaces:
{ id: "ws_001", name: "Finance", active_config_id: "cfg_A" }

configs:
{ id: "cfg_A", workspace_id: "ws_001", status: "active",   title: "Baseline v1", version: "0.0.3" }
{ id: "cfg_B", workspace_id: "ws_001", status: "inactive", title: "Experiment",   version: "0.0.1" }
{ id: "cfg_C", workspace_id: "ws_001", status: "archived", title: "Old",          version: "0.0.2" }
```

**Folder**

```
data/configs/cfg_A/
  manifest.json
  on_job_start.py
  columns/
    member_id.py
    invoice_total.py
```

**`columns/member_id.py`**

```python
def detect_header(*, header, values, column_index, table, job_context, env):
    return {"scores": {"self": 1.0}} if header and "member" in header.lower() else {"scores": {}}

def detect_id_shape(*, header, values, column_index, table, job_context, env):
    vals = [str(v).strip() for v in values if str(v).strip()]
    ok = vals and all(v.isalnum() and 6 <= len(v) <= 12 for v in vals[:50])
    return {"scores": {"self": 0.6 if ok else 0.0, "job_id": -0.2 if ok else 0.0}}

def transform(*, header, values, column_index, table, job_context, env):
    return {"values": [ (str(v).strip().upper() or None) if v is not None else None for v in values ]}
```

---

## 12) Acceptance criteria (v0.5)

* Configs live under `data/configs/<id>` with **manifest v0.5** and column modules implementing **`detect_*` + `transform`**.
* API provides **create/clone/import/export**, **manifest/files edit**, **validate**, **activate**, **archive/unarchive**, and **secrets** management.
* Exactly **one active** config per workspace is enforced; only **inactive** configs are editable.
* Validation rejects plaintext secrets and missing or malformed modules; runtime executes hooks/columns in sandbox with env+secrets injected.
* Jobs run the **detect → assign (greedy) → transform** pipeline; warnings/mapping available to callers.

---
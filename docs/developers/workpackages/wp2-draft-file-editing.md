# docs/developers/workpackages/wp2-draft-file-editing.md

# WP‑2 — Config Builder: simplest standard REST for editing + validate + export

## Goal (one paragraph)

Expose a **minimal, conventional REST API** so the web editor can: list the **entire** draft tree in one call, fetch file bytes **on demand**, edit locally with a **dirty** cache, and save via **per‑file PUTs** guarded by **ETag**. Add **Validate** to compute a deterministic `content_digest` and return issues (Build will validate again), and **Export** to download a ZIP. Provide a tiny **create-directory** endpoint so the UI can create empty folders; otherwise directories are implied by file paths.

---

## Route index (all the UI needs)

Base prefix:

```
/api/v1/workspaces/{workspace_id}/configurations/{config_id}
```

**Config**

* `GET    /api/v1/workspaces/{ws}/configurations/{cfg}` — metadata (status, digest, updated_at)

**Files & directories**

* `GET    /api/v1/workspaces/{ws}/configurations/{cfg}/files` — full tree (files + dirs), one call
* `GET    /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}` — read file (raw bytes; JSON optional)
* `PUT    /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}` — create/update file (raw bytes; parents auto‑create; ETag preconditions)
* `DELETE /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}` — delete file (ETag)
* `POST   /api/v1/workspaces/{ws}/configurations/{cfg}/directories/{*path}` — create **empty** directory
* `DELETE /api/v1/workspaces/{ws}/configurations/{cfg}/directories/{*path}` — delete directory (`?recursive=1` allowed)

**Workflow helpers**

* `POST   /api/v1/workspaces/{ws}/configurations/{cfg}/validate` — compute `content_digest`, return issues
* `GET    /api/v1/workspaces/{ws}/configurations/{cfg}/export?format=zip` — ZIP of the editable tree

> **Not required now:** import. Add later as `POST /…/import` with a ZIP body.

---

## Behavior & guardrails (consistent across routes)

* **Editability:** only `status='draft'` is writable. Writes in `active`/`inactive` → `409 Conflict` (`code: "config_not_editable"`). Reads are allowed in any state.
* **Root:** `${ADE_CONFIGS_DIR}/{workspace_id}/config_packages/{config_id}/`
* **Editable set (include):** `src/ade_config/**`, `manifest.json`, `pyproject.toml` (optional), `config.env` (optional), `assets/**`
* **Exclude:** `.git/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `.venv/`, `venv/`, `env/`, `node_modules/`, `.idea/`, `.vscode/`, `dist/`, `build/`
* **Path hygiene:** `path` is POSIX‑relative (no leading `/`), normalized, must remain under the config root **and** within the editable set. **Deny symlinks** (files or dirs).
* **ETags:** strong per‑file ETag = `sha256(file bytes)` (quoted in HTTP headers).

  * **Create:** `If-None-Match: *`
  * **Update/Delete:** `If-Match: "<etag>"`
  * On mismatch: `412 Precondition Failed` + `ETag` of current version.
* **Writes:** atomic (temp → fsync → rename). On any successful write, bump `updated_at` in the config row.
* **Sizes:** code/config files ≤ **512 KiB**; `assets/**` ≤ **5 MiB** → `413 Payload Too Large`.
* **Validate:** returns `content_digest` + issues; we **do not** store a “last validated” timestamp. **Build** will always validate again internally.

---

## Endpoint details

### 1) Config metadata

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}
Accept: application/json
```

**200**

```json
{
  "workspace_id": "ws_123",
  "config_id": "01JC0M8YH1Y7A6RNK3Q3JK22QX",
  "display_name": "Membership v2",
  "status": "draft",
  "config_version": 0,
  "content_digest": "sha256:ab12cd34…",   // may be null before first validate
  "updated_at": "2025-11-10T14:20:31Z"
}
```

---

### 2) Full tree (one call)

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}/files
Accept: application/json
```

**200**

```json
{
  "root": "",
  "entries": [
    {"path":"manifest.json","type":"file","size":752,"mtime":"2025-11-10T14:24:03Z","etag":"\"sha256:3b1e…\""},
    {"path":"src/ade_config","type":"dir"},
    {"path":"src/ade_config/column_detectors/email.py","type":"file","size":3142,"mtime":"2025-11-10T14:24:03Z","etag":"\"sha256:7f6d…\""}
  ]
}
```

> Frontend builds the sidebar from this flat list. Re‑list when needed (e.g., after Save/Import).

---

### 3) Read file

**Raw bytes (canonical)**

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}
Accept: application/octet-stream
# Optional: If-None-Match: "<etag>" to allow 304
```

**200** with bytes. Headers: `ETag`, `Last-Modified`, `Content-Type`.
**304** if unchanged.

**JSON convenience (optional for SPAs)**

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}?format=json
Accept: application/json
```

**200**

```json
{
  "path": "src/ade_config/column_detectors/email.py",
  "encoding": "utf-8",                // or "base64" when binary
  "content": "import re\nEMAIL = ...\n",
  "etag": "\"sha256:7f6d…\"",
  "size": 3142,
  "mtime": "2025-11-10T14:24:03Z"
}
```

---

### 4) Create / Update file (one verb, idempotent)

Parents auto‑create inside the editable set via `?parents=1`.

**Create**

```http
PUT /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}?parents=1
If-None-Match: *
Content-Type: application/octet-stream

<file bytes>
```

**Update**

```http
PUT /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}
If-Match: "sha256:OLD"
Content-Type: application/octet-stream

<file bytes>
```

**200 / 201** with headers `ETag`, `Last-Modified`. JSON body (optional):

```json
{ "path":"…", "size":3201, "mtime":"2025-11-10T14:36:52Z", "etag":"\"sha256:BEEF…\"" }
```

**Errors:** `428 precondition_required`, `412 precondition_failed`, `409 config_not_editable`, `403 path_not_allowed`, `400 invalid_path`, `413 payload_too_large`.

> **Rename**: do `PUT` new path (create) then `DELETE` old path; no separate move API required.

---

### 5) Delete file

```http
DELETE /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}
If-Match: "sha256:OLD"
```

**204 No Content**

---

### 6) Create / Delete directory (tiny convenience)

Empty directories don’t exist until a file is written. Provide these to support a “New Folder” and “Delete Folder” button:

Create empty dir:

```http
POST /api/v1/workspaces/{ws}/configurations/{cfg}/directories/{*path}
```

**201 Created**

Delete dir (defaults to empty‑only; allow recursive with `?recursive=1`):

```http
DELETE /api/v1/workspaces/{ws}/configurations/{cfg}/directories/{*path}?recursive=1
```

**204 No Content**

---

### 7) Validate (digest + issues)

```http
POST /api/v1/workspaces/{ws}/configurations/{cfg}/validate
```

**200**

```json
{
  "content_digest": "sha256:ab12cd34…",
  "issues": []
}
```

> We don’t store “last validated”. **Build** always validates again internally.

---

### 8) Export (ZIP)

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}/export?format=zip
Accept: application/zip
```

**200** `application/zip`
Headers: `Content-Disposition: attachment; filename="{config_id}.zip"`

ZIP contains only the **editable set** (same include/exclude rules), preserving relative paths.

---

## Frontend flow (simple & standard)

1. **Open builder**

   * `GET /configurations/{cfg}` → check `status`.
   * `GET /files` → render full tree (cache per‑file ETags).

2. **Open a tab**

   * `GET /files/{path}` → keep `{bytes, etag}` in local cache.

3. **Edit locally**

   * Mark tab **dirty**; no server calls while typing.

4. **Save**

   * For each dirty tab:

     * New → `PUT` with `If-None-Match: *`
     * Existing → `PUT` with `If-Match: "<etag>"`
     * On `412`, fetch latest, show diff/merge, retry with new ETag.
   * Re‑list `GET /files` if you want to refresh the sidebar.

5. **Folders**

   * “New Folder” → `POST /directories/{path}`
   * “Delete Folder” → `DELETE /directories/{path}?recursive=1` (or ensure empty first)

6. **Validate / Export**

   * Validate on demand: `POST /validate`
   * Export when needed: `GET /export?format=zip`

---

## Status codes (uniform)

* **200 OK**, **201 Created**, **204 No Content**
* **304 Not Modified** (GET file with `If-None-Match`)
* **400 invalid_path**, **403 path_not_allowed**, **404 not_found**
* **409 config_not_editable**
* **412 precondition_failed** (ETag mismatch)
* **413 payload_too_large**
* **428 precondition_required** (missing `If‑Match` / `If‑None‑Match`)

Error body format:

```json
{ "code": "precondition_failed", "message": "ETag mismatch", "current_etag": "\"sha256:…\"" }
```

---

## Why this is the simplest thing that works

* **Three file verbs** (GET/PUT/DELETE) plus a **directory create** convenience cover “upload files, create folders, etc.” without custom protocols.
* **Raw bytes** in `PUT`/`GET` match how browsers upload/download files (no base64 required). The JSON read format remains available for SPAs.
* **ETag preconditions** are standard and prevent clobbering; no server locks or websockets needed.
* A single **full‑tree listing** keeps the sidebar instant and avoids paginated recursion.

If you want this even leaner, you can *skip* the directory endpoints and rely on `PUT ?parents=1`—but most editors include a “New Folder” button, so keeping `POST /directories/{path}` is pragmatic and still simple.

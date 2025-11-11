# docs/developers/workpackages/wp2-draft-file-editing.md

# WP‑2 — Config Builder File Editing (frontend‑first, standard REST)

## What we’re building (one paragraph)

A **draft** configuration is a small folder of files the user edits in the browser. The frontend renders the **entire tree** once, loads individual files on demand, keeps a **local cache** (content + ETag), and marks tabs **dirty** while the user types. On **Save**, the frontend issues **per‑file** `PUT`/`DELETE` requests guarded by **HTTP ETags** (`If‑Match` / `If‑None‑Match`) so we never overwrite someone else’s changes. The **Validate** endpoint (from WP‑1) remains a separate, explicit action to compute `content_digest` before any build.

---

## Frontend mental model

* **Initial load**: fetch config metadata (status, timestamps) and a **full recursive tree** in one call; render the sidebar.
* **Open file**: GET content for a file; cache `{content, etag}`. Editing only changes local state and sets `dirty=true`.
* **Save**: loop over dirty files and call `PUT` (or `DELETE`) **per file** with ETag preconditions. Update cached `etag` from the response; clear `dirty`.
* **Conflict** (`412`): fetch the latest server version, show a diff/merge, retry with the new ETag.
* **Validate**: when the user clicks Validate, call `POST /validate` to snapshot `content_digest` and surface issues.

This is the same pattern used by GitHub’s Contents API and many web IDEs: small, predictable REST calls and standard caching headers.

---

## States & guardrails

* **Only `draft` is writable.** Any write in `active` or `inactive` → `409 Conflict` (`code: "config_not_editable"`).
* **Edits update** `configurations.updated_at`. They **do not** change `content_digest`/`validated_at` (only **Validate** does).
* **Paths are safe**: POSIX‑relative, no `..`, no absolute paths; path must resolve under the config root; **deny symlinks**.

---

## Resource layout (server)

All routes are rooted at:

```
/api/v1/workspaces/{workspace_id}/configurations/{config_id}
```

**Editable set** (enforced server‑side):

* Include: `src/ade_config/**`, `manifest.json`, `pyproject.toml?`, `config.env?`, `assets/**`
* Exclude: `.git/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `.venv/`, `venv/`, `env/`, `node_modules/`, `.idea/`, `.vscode/`, `dist/`, `build/`
* Deny: any **symlink** (file/dir), traversal, or absolute paths.

**Size caps** (defaults): code files ≤ **512 KiB**; `assets/**` ≤ **5 MiB**.

---

## Standard endpoints (what the frontend will call)

### 0) Get config metadata (status + timestamps)

Used to gate editing and show “needs validate” badges.

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
  "content_digest": null,
  "validated_at": null,
  "updated_at": "2025-11-10T14:20:31Z"
}
```

---

### 1) List full tree (one call, recursive)

Returns **all** files and directories. Clients can build a nested view from this flat list.

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}/files
Accept: application/json
```

**200**

```json
{
  "root": "",
  "entries": [
    {"path":"manifest.json","type":"file","size":752,"mtime":"2025-11-10T14:24:03Z","etag":"\"3b1e…\""},
    {"path":"pyproject.toml","type":"file","size":891,"mtime":"2025-11-10T14:24:03Z","etag":"\"a94a…\""},
    {"path":"src/ade_config","type":"dir"},
    {"path":"src/ade_config/column_detectors","type":"dir"},
    {"path":"src/ade_config/column_detectors/email.py","type":"file","size":3142,"mtime":"2025-11-10T14:24:03Z","etag":"\"7f6d…\""},
    {"path":"assets","type":"dir"}
  ]
}
```

*Errors*: `400 invalid_path`, `404 config_not_found`. (Reads are allowed in any state.)

---

### 2) Read a file (text by default; raw on request)

Default returns JSON with UTF‑8 text. To stream raw bytes, set `Accept: application/octet-stream`.

```http
GET /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}
```

**200 (JSON, text)**

```
ETag: "7f6d…"
Content-Type: application/json
```

```json
{
  "path": "src/ade_config/column_detectors/email.py",
  "encoding": "utf-8",
  "content": "import re\nEMAIL = re.compile(r\"…\", re.I)\n",
  "size": 3142,
  "mtime": "2025-11-10T14:24:03Z",
  "etag": "\"7f6d…\""
}
```

**200 (raw)**

```
Accept: application/octet-stream
ETag: "9f8e…"

<bytes>
```

*Errors*: `400 invalid_path`, `403 path_not_allowed`, `404 not_found`.

---

### 3) Create / Update a file (idempotent `PUT` with preconditions)

Parents are auto‑created. Use **one of** the standard HTTP preconditions:

* **Create**: `If-None-Match: *`
* **Update**: `If-Match: "<etag>"` (from last GET/PUT)

```http
PUT /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}
Content-Type: application/json
If-Match: "7f6d…"            # updating an existing file
# or
If-None-Match: *             # creating new
```

**Request (text)**

```json
{
  "encoding": "utf-8",
  "content": "import re\n# edited\n"
}
```

**Request (binary)**

```json
{
  "encoding": "base64",
  "content": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**200 OK** (updated) or **201 Created** (new)

```
ETag: "beef…"
Content-Type: application/json
```

```json
{
  "path": "src/ade_config/column_detectors/email.py",
  "size": 3201,
  "mtime": "2025-11-10T14:36:52Z",
  "etag": "\"beef…\""
}
```

*Errors*:
`428 Precondition Required` (missing `If-Match`/`If-None-Match`)
`412 Precondition Failed` (ETag mismatch; include `current_etag` header/body)
`409 config_not_editable` (not draft)
`403 path_not_allowed` · `400 invalid_path` · `413 payload_too_large`

---

### 4) Delete a file (guarded by ETag)

```http
DELETE /api/v1/workspaces/{ws}/configurations/{cfg}/files/{*path}
If-Match: "7f6d…"
```

**204 No Content**

*Errors*: `428` (missing precondition), `412` (ETag mismatch), `404`, `409 config_not_editable`.

> **Renames:** perform **copy + delete**: `PUT` new path (with `If-None-Match: *`) then `DELETE` old path (with `If-Match`). No custom “move” verb needed.

---

### 5) Validate (snapshot digest, required before build)

Same endpoint from WP‑1; included here so the editor can wire the button.

```http
POST /api/v1/workspaces/{ws}/configurations/{cfg}/validate
```

**200**

```json
{
  "workspace_id": "ws_123",
  "config_id": "01JC0M8YH1Y7A6RNK3Q3JK22QX",
  "content_digest": "sha256:ab12cd34…",
  "validated_at": "2025-11-10T15:03:12Z",
  "issues": []
}
```

---

## ETags & caching (how the frontend should use them)

* Store the `etag` returned by every GET/PUT in your file cache.
* On **Save**, send `If-Match` with that etag (or `If-None-Match: *` for new files).
* On **412**, fetch the latest file to get the **server etag** + **server content**, show a diff/merge, then retry with the new ETag.
* For **fast open**, you may issue GET with `If-None-Match: "<etag>"` to get `304 Not Modified`.

---

## Frontend data model (suggested)

```ts
type FileEntry = {
  path: string;
  type: 'file' | 'dir';
  size?: number;
  mtime?: string;
  etag?: string;        // for files
};

type FileTab = {
  path: string;
  encoding: 'utf-8' | 'base64';
  content: string;      // text or base64
  etag: string;         // last known server etag
  dirty: boolean;
  lastFetchedAt: number;
};
```

**Save All (pseudo‑code):**

```ts
for (const tab of openTabs.filter(t => t.dirty)) {
  const hdrs = tab.isNew ? {'If-None-Match': '*'} : {'If-Match': tab.etag};
  const body = { encoding: tab.encoding, content: tab.content };
  const res = await fetch(PUT `/files/${encode(tab.path)}`, { headers: hdrs, body: JSON.stringify(body) });

  if (res.status === 200 || res.status === 201) {
    tab.etag = res.headers.get('ETag')!;
    tab.dirty = false;
  } else if (res.status === 412) {
    const latest = await fetch(GET `/files/${encode(tab.path)}`).then(r => r.json());
    // show diff (tab.content vs latest.content), user resolves, then retry with If-Match: latest.etag
  } else {
    // surface error toast; leave tab dirty
  }
}
```

---

## Error responses (uniform JSON body)

Return standard HTTP codes with a compact JSON payload:

```json
{ "code": "precondition_failed", "message": "ETag mismatch", "current_etag": "\"9f8e…\"" }
```

Common codes:
`200/201/204`, `304`, `400 invalid_path`, `403 path_not_allowed`, `404 not_found`,
`409 config_not_editable`, `412 precondition_failed`, `413 payload_too_large`, `428 precondition_required`.

---

## Acceptance (for both sides)

* **Full tree** returns all paths (files + dirs) with sizes, mtimes, and file ETags.
* **GET /files/{path}** returns text JSON by default and raw bytes when `Accept: application/octet-stream`.
* **Per‑file PUT/DELETE** with ETag preconditions works; conflicts return `412` with the current ETag.
* **Writes only in draft**; reads allowed in any state.
* Paths are safe; no symlinks; excluded directories are never touched.
* `updated_at` changes on successful writes; `content_digest` only changes on **Validate**.

This is a straight‑ahead, **non‑bespoke** REST interface that frontends already know how to use: list everything once, edit locally, and save each file back with standard HTTP preconditions.

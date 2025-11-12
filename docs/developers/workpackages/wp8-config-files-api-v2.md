```markdown
# WP‑8 — Config Files API v2 — Backend Endpoint Redesign (Workpackage)

**Audience:** Backend API owners, reviewers, QA  
**Goal:** Ship a predictable, standards‑compliant Files API (FastAPI) that frontends can reliably type‑gen via `openapi-typescript`, render trees with minimal branching, and perform safe edits/renames with first‑class HTTP caching & concurrency controls.

---

## 1) Objectives

- **Typed, cache‑friendly listing** that UIs can diff quickly (flat entries with `parent`, `name`, `depth`, `has_children`) and a weak list `ETag` for `304 Not Modified`.
- **Uniform write shape** (201/200 share the same JSON body) with strong per‑item `ETag` for safe conditional writes.
- **Atomic rename/move** with source precondition and optional destination precondition to prevent blind clobbers.
- **Standards first**: content negotiation (`Accept`), Range requests, `ETag`/`If-Match`/`If-None-Match`, `Location` header, RFC 9457 `application/problem+json` errors.
- **OpenAPI 3.1 contract** tuned for clean type generation (no unnecessary unions, discriminators avoided unless useful).

---

## 2) Scope / Non‑Goals

**In scope**
- GET list, GET bytes/JSON, PUT write, PATCH move/rename, DELETE file/dir, HEAD metadata.
- Include/exclude globs, pagination, sorting, stable error codes.
- Limits enforcement (code vs asset sizes), path hygiene, editability/capabilities.

**Out of scope**
- Batch reads/writes, server‑push logs/SSE, language‑aware features (e.g., AST/linters).

---

## 3) Cross‑Cutting Behavior

- **Resource base:** `/api/v1/workspaces/{workspace_id}/configurations/{config_id}`
- **JSON field style:** `snake_case`.
- **Content negotiation:**  
  - Default read → `application/octet-stream` (bytes).  
  - `Accept: application/json` → JSON helper with inline text, metadata.  
  - (Optional compat) `?format=json` may map to JSON helper but **header is canonical**.
- **Caching & concurrency:**  
  - **Listings:** Weak `ETag: W/"<fileset-hash>"`, honor `If-None-Match` → `304`.  
  - **Items:** Strong `ETag: "<opaque>"`, honor `If-Match` for update/delete/rename; `If-None-Match: *` for create.
- **Pagination:** `limit` + `page_token`; also emit `Link: <…>; rel="next"`. Body includes `next_token`.
- **Errors:** `application/problem+json` (RFC 9457). Always include a stable machine `code`.
- **Security:** Existing Workspace.Configs authorization; reject symlinks, traversal; enforce editable status.
- **Time formats:** ISO‑8601 UTC (`Z`) in bodies; `Last-Modified` for items.
- **Directory normalization:** Directory paths end with `/`. Root is `""`.

---

## 4) API Contract (endpoints & semantics)

### 4.1 List files
```

GET /workspaces/{workspace_id}/configurations/{config_id}/files

```
**Query**
- `prefix`: string (default `""`) — subtree root to list.
- `depth`: `"0" | "1" | "infinity"` — WebDAV‑like semantics. `"0"` = only this dir; `"1"` = one level; `"infinity"` = full subtree.
- `include`: repeatable glob(s) (optional).
- `exclude`: repeatable glob(s) (optional).
- `limit`: int (1..5000; default 1000).
- `page_token`: string (opaque; optional).
- `sort`: `path | name | mtime | size` (default `path`).
- `order`: `asc | desc` (default `asc`).

**Request headers (optional)**
- `If-None-Match: W/"<fileset-hash>"`

**Success**
- `200 application/json` → **FileListing** (below)  
  Headers: `ETag: W/"<fileset-hash>"`, `Cache-Control: private, must-revalidate`  
- `304 Not Modified` (no body) when list unchanged.

**Notes**
- `fileset_hash` is a stable digest over sorted `(path, etag, size)` tuples; algorithm is intentionally opaque.
- `has_children` is a cheap existence probe to draw expanders without fetching deeper.

---

### 4.2 Read file (bytes or JSON helper)
```

GET /workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}

```
**Request headers (optional)**
- `Accept: application/json` for JSON helper, otherwise bytes.
- `Range: bytes=start-end` for partial reads.

**Success**
- Bytes:
  - `200 application/octet-stream` (full) or `206` with `Content-Range`.
  - Headers: `ETag`, `Last-Modified`, `Content-Type`.
- JSON helper:
  - `200 application/json` → **FileReadJson** (inline text + metadata).
  - Headers: `ETag`, `Last-Modified`.

---

### 4.3 Metadata probe
```

HEAD /workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}

```
**Success:** `200` with `ETag`, `Last-Modified`, `Content-Type`, `Content-Length`. No body.

---

### 4.4 Write (create/update)
```

PUT /workspaces/{workspace_id}/configurations/{config_id}/files/{file_path}?parents=true
Content-Type: application/octet-stream

```
**Preconditions**
- **Create:** `If-None-Match: *` (required; else `428 precondition_required`).
- **Update:** `If-Match: "<current-etag>"` (required; else `428`).

**Success**
- **Create:** `201 application/json` → **FileWriteResponse**; headers: `ETag`, `Location: /…/files/{file_path}`.
- **Update:** `200 application/json` → **FileWriteResponse**; header: `ETag`.

**Semantics**
- Server writes to temp, `fsync`, atomic replace.
- Enforce size limits (code ≤ 512 KiB; `assets/**` ≤ 5 MiB).

---

### 4.5 Rename / Move (atomic)
```

PATCH /workspaces/{workspace_id}/configurations/{config_id}/files/{from_path}
Content-Type: application/json
If-Match: "<source-etag>"

````
**Body**
```json
{ "op": "move", "to": "dest/path.ext", "overwrite": false, "dest_if_match": "\"<dest-etag>\"" }
````

* `overwrite` default `false`. If `true`, require `dest_if_match` (or the server may also accept `If-None-Match: *` on dest semantics) to avoid blind clobber.
* Directory moves permitted when `from_path` and `to` both end with `/`.

**Success**

* `200 application/json` → **FileRenameResponse** (new `etag` of moved item).

---

### 4.6 Delete

```
DELETE /workspaces/{workspace_id}/configurations/{config_id}/files/{path}
```

**Preconditions**

* `If-Match` strongly recommended; **required for directories**.

**Success**

* `204 No Content`

**Failure**

* `409 directory_not_empty` for non‑empty directories.

---

## 5) Models (canonical JSON payloads)

> These schemas are intentionally **single‑shape** (no `oneOf`) so `openapi-typescript` generates straightforward types. For `depth`, the query parameter uses the string union `"0" | "1" | "infinity"`; entries carry numeric `depth` for indenting.

### 5.1 `FileEntry`

```json
{
  "path": "src/ade_config/_shared.py",
  "name": "_shared.py",
  "parent": "src/ade_config/",
  "kind": "file",                   // "file" | "dir"
  "depth": 2,                       // 0 for root-level entries
  "size": 1296,                     // null for directories
  "mtime": "2025-11-10T22:40:59Z",
  "etag": "\"510-01ab…\"",          // strong, opaque
  "content_type": "text/x-python",  // "inode/directory" for dirs
  "has_children": false
}
```

### 5.2 `FileListing`

```json
{
  "workspace_id": "ws_123",
  "config_id": "cfg_abc",
  "status": "draft",                 // "draft" | "published" | "archived"
  "capabilities": {
    "editable": true,
    "can_create": true,
    "can_delete": true,
    "can_rename": true
  },
  "root": "",                        // actual prefix listed
  "prefix": "",                      // alias for S3-like familiarity
  "depth": "infinity",
  "generated_at": "2025-11-11T18:12:30Z",
  "fileset_hash": "c7f0b3e1…",       // weak list ETag token
  "summary": { "files": 47, "directories": 9 },
  "limits": { "code_max_bytes": 524288, "asset_max_bytes": 5242880 },
  "count": 7,
  "next_token": null,
  "entries": [ /* FileEntry[] */ ]
}
```

### 5.3 `FileReadJson`

```json
{
  "path": "src/ade_config/column_detectors/email.py",
  "encoding": "utf-8",
  "content": "import re\nEMAIL = ...\n",
  "size": 3421,
  "mtime": "2025-11-10T22:10:02Z",
  "etag": "\"7f6d…\"",
  "content_type": "text/x-python"
}
```

### 5.4 `FileWriteResponse`

```json
{
  "path": "src/ade_config/column_detectors/email.py",
  "created": false,
  "size": 3510,
  "mtime": "2025-11-11T19:59:03Z",
  "etag": "\"babe…\""
}
```

### 5.5 `FileRenameRequest`

```json
{ "op": "move", "to": "src/ade_config/column_detectors/email.py", "overwrite": false }
```

### 5.6 `FileRenameResponse`

```json
{
  "from": "src/ade_config/column_detectors/emal.py",
  "to": "src/ade_config/column_detectors/email.py",
  "size": 3421,
  "mtime": "2025-11-11T18:21:03Z",
  "etag": "\"7f6d…\""
}
```

### 5.7 Problem Details (errors)

```json
{
  "type": "about:blank",
  "title": "Precondition Failed",
  "status": 412,
  "detail": "ETag mismatch",
  "code": "precondition_failed",
  "trace_id": "7c6e8b9f3b5c",
  "meta": { "current_etag": "\"7f6d…\"" }
}
```

**Canonical error `code` set (stable):**

* `precondition_required`, `precondition_failed`, `config_not_editable`,
* `file_not_found`, `invalid_path`, `path_not_allowed`,
* `dest_exists`, `directory_not_empty`,
* `payload_too_large`, `unsupported_media_type`,
* `forbidden`, `unauthorized`, `rate_limited`.

---

## 6) Validation & Guardrails

* **Editability:** Only `status="draft"` allows writes; others → `409 config_not_editable`.
* **Path hygiene:** POSIX‑relative, UTF‑8, normalized, no leading `/`, no `..`, no symlinks, within editable roots.
* **Size limits:** code/config ≤ **512 KiB**; `assets/**` ≤ **5 MiB** → `413 payload_too_large`.
* **MIME types:** `mimetypes.guess_type` fallback to `application/octet-stream`; directories use `inode/directory`.
* **Sorting:** server‑side stable; default `path asc`.

---

## 7) Backward Compatibility & Migration

* **Reads:** continue to support `?format=json`, but recommend `Accept: application/json`.
* **Writes:** 201 previously without body → now returns **FileWriteResponse**; legacy clients may ignore body safely.
* **Rename:** new `PATCH` endpoint. If a legacy client sees `404/405`, it may fall back to PUT+DELETE (not recommended).
* **Errors:** all file endpoints now return `application/problem+json`.

---

## 8) Acceptance Criteria

* Listing honors `If-None-Match` and returns `304` when unchanged; `fileset_hash` stable across pagination windows.
* UI can render a large tree without additional fetches using `parent`, `depth`, `has_children`.
* Writes (create/update) always return **FileWriteResponse** with correct `ETag` and `Location` on `201`.
* Rename is atomic and enforces source `If-Match`; destination conflicts handled via `overwrite`/`dest_if_match`.
* All endpoints emit RFC 9457 Problem Details with stable `code`s on failure.
* Range reads (`206`) work with correct `Content-Range` and `ETag`.

---

## 9) Test Plan (representative)

**Unit**

* `fileset_hash` determinism given reordered input; ignores non‑material fields.
* Path normalization / invalid path rejection (leading slash, traversal, symlink).
* Size limit enforcement per prefix (`assets/**` vs code).
* Rename: happy path, dest exists with/without `overwrite`, dir rename.

**Integration (FastAPI)**

* List: depth `"0"|"1"|"infinity"`, include/exclude globs, pagination, sorting; `304` when `If-None-Match` matches.
* Read: bytes vs JSON helper; `Range` → `206` correctness; headers present.
* Write: create (`If-None-Match:*`) vs update (`If-Match`), ETag changes; 201 `Location`.
* Delete: file vs non‑empty dir; `If-Match` enforcement on dir.
* Errors: verify `problem+json` schema and `code` mapping.

**Regression (UI smoke)**

* Expand/collapse tree uses `has_children` without extra calls.
* Edit+save round‑trip minimal; rename with conflict; refresh + hash check avoids redundant re-renders.

---

## 10) Rollout / Observability

* Emit `X-Request-Id` / trace id; include in `problem+json`.
* Metrics: request counts, latency (p95), bytes served, hit rate for `304`, `412` frequency, rename conflicts.
* Slow‑path logs with redaction for large payloads.

### `.workpackage/packages/0011-backend-configurations-jobs-redesign/attachments/design.md`

# Backend configurations/jobs redesign (v1)

> **Goal:** Make configuration authoring/versioning simple and bulletproof with a **version-snapshot** model. Every job binds to a specific immutable version. No per-file versioning. `startup.py` is reserved for installing deps only (no persisted artifacts in v1).

---

## 0) What we’re building (in one paragraph)

A workspace-scoped **Configuration** contains a small tree of scripts (`startup.py`, `run.py`, `columns/<key>.py`, optional `table/transform.py`, `table/validators.py`) plus a **manifest**. Authors edit a single **draft**; **publish** freezes a snapshot into an immutable **version**. Jobs reference that **config_version_id**, ensuring determinism and easy rollback. We replace the legacy `/configurations` schema and API with a **version-centric** core: `configs`, `config_versions`, `config_files`.

---

## 1) Core concepts & lifecycle

- **Configuration (package)** — workspace-scoped logical unit.
- **Version (snapshot)** — immutable; contains the manifest and all files at publish time.
- **Draft** — one mutable version per configuration.
- **Publish** — copies the draft → new immutable version row; computes `files_hash`; assigns semantic `semver`.
- **Run lifecycle (per job)** — `Extract → run_start → Prepare (per column) → Detect → Map (Hungarian, min_score) → Transform (column → optional table) → Validate → run_end`.

**Notes:**
- `startup.py` exists to install dependencies only in v1; engine does not persist outputs from it.
- No per-file versioning; a version is a complete snapshot.

---

## 2) Database schema (SQLite, modify `0001_initial_schema.py` in place)

### Tables

**configs**
- `id TEXT PK`, `workspace_id TEXT NOT NULL`, `slug TEXT NOT NULL`, `title TEXT NOT NULL`
- `created_by TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL`
- `UNIQUE(workspace_id, slug)`

**config_versions**
- `id TEXT PK`, `config_id TEXT NOT NULL`, `semver TEXT NOT NULL`
- `status TEXT NOT NULL CHECK (status IN ('draft','published','deprecated'))`
- `message TEXT NULL`
- `manifest_json TEXT NOT NULL`  _(JSON string)_
- `files_hash TEXT NOT NULL`      _(sha256 of concatenated per-file shas; empty string allowed for brand-new drafts)_
- `created_by TEXT NULL`, `created_at TIMESTAMPTZ NOT NULL`, `published_at TIMESTAMPTZ NULL`
- `UNIQUE(config_id, semver)`
- **Index (partial unique):** one draft per config  
  `CREATE UNIQUE INDEX cv_one_draft_per_config ON config_versions(config_id) WHERE status='draft';`
- **Index (partial unique):** one published per config  
  `CREATE UNIQUE INDEX cv_one_published_per_config ON config_versions(config_id) WHERE status='published';`

**config_files**
- `id TEXT PK`, `config_version_id TEXT NOT NULL`
- `path TEXT NOT NULL`, `language TEXT NOT NULL DEFAULT 'python'`
- `code TEXT NOT NULL`, `sha256 TEXT NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `UNIQUE(config_version_id, path)`

**jobs** (changes)
- Add `config_version_id TEXT NULL` (FK → `config_versions.id`)
- Add `run_key TEXT NULL`  _(sha of doc_sha | files_hash | flags | resource_versions (empty in v1))_
- Plan to drop legacy `configuration_id` usage in services and APIs.

**Remove legacy tables**
- `configurations`, `configuration_script_versions`, `configuration_columns`.

**SQLite tips**
- Use `sqlite_where=sa.text("status = 'draft'")` / `sqlite_where=sa.text("status = 'published'")` in Alembic for partial uniques.
- Keep enums as TEXT + CHECK constraints (as above).

---

## 3) Manifest (stored as JSON string in `config_versions.manifest_json`)

Minimum shape (v1):

```json
{
  "name": "Example Config",
  "sdk_version": "0.1.0",
  "min_score": 1.0,
  "columns": [
    { "key": "postal_code", "label": "Postal Code", "path": "columns/postal_code.py", "ordinal": 1, "required": true, "enabled": true, "depends_on": [] }
  ],
  "table": {
    "transform": { "path": "table/transform.py" },
    "validators": { "path": "table/validators.py" }
  },
  "hints": { "header_row": null, "header_row_contains": [], "sheets": { "include": [], "exclude": [] } },
  "pins": {},
  "capabilities": { "allow_network": false, "allow_llm": false, "resources": {} },
  "files_hash": ""
}
````

**Invariants**

* Every `columns[i].path` must exist as a file in the version at publish time.
* `files_hash` is recalculated from the draft files whenever a draft file changes.
* `ordinal` is unique within the config’s draft.

---

## 4) API (version-centric; replace `/configurations/**`)

**Packages**

* `GET /api/v1/workspaces/:ws/configs` — list
* `POST /api/v1/workspaces/:ws/configs` — create `{slug,title}` → returns config with a new draft
* `GET /api/v1/workspaces/:ws/configs/:configId` — details
* `DELETE /api/v1/workspaces/:ws/configs/:configId` — delete (only if no published versions or with force flag)

**Versions**

* `GET /api/v1/workspaces/:ws/configs/:configId/versions` — list versions (draft/published/deprecated)
* `POST /api/v1/workspaces/:ws/configs/:configId/publish` — `{semver, message}` → freeze draft → published
* `POST /api/v1/workspaces/:ws/configs/:configId/revert` — switch last published back (deprecate current)

**Draft files**

* `GET /.../draft/files` → `[{path, sha256, language}]`
* `GET /.../draft/files/:path` → `{code, sha256}`
* `POST /.../draft/files` → `{path, template?}`
* `PUT /.../draft/files/:path` → `{code}` + header `If-Match: <sha256>`
* `DELETE /.../draft/files/:path`

**Draft manifest**

* `GET /.../draft/manifest` → manifest JSON
* `PATCH /.../draft/manifest` → partial merge + validation

**Plan & Dry-run**

* `POST /.../draft:plan` → `{"phases":["extract","run_start","prepare","detect","map","transform","transform_table","validate","run_end"], "dag":[...], "warnings":[...] }`
* `POST /.../draft:dry-run` → body `{documentId}`; returns mapping matrix (scores + assignments), findings, metrics, logs

**Jobs**

* Submit using `config_version_id` (not `configuration_id`).

**Error semantics**

* `412 Precondition Failed` on ETag mismatch during draft file PUT.
* `409 Conflict` if trying to create a second draft/published.
* `400 Bad Request` on manifest validation failure.

---

## 5) Runner (dry-run + jobs)

**Order**

1. `Extract` → XLSX → candidate tables
2. `run_start` → create per-run clients in memory (if needed)
3. `Prepare` (per column) → compile regex, small dicts, etc.
4. `Detect` → produce score deltas per (physical, canonical)
5. `Map` → Hungarian (maximize total score); drop matches `< min_score`; ties break by feature count, then left-to-right index
6. `Transform` → prefer `transform_column`, fallback `transform_cell`
7. `transform_table` (optional)
8. `Validate` → columns then table
9. `run_end` → close clients

**Scoring/Hungarian**

* Normalize feature contributions to integers (e.g., ×100) before assignment to avoid FP noise.
* Allow negative scores to penalize mismatches.

**run_key**

* `run_key = sha256(doc_sha | files_hash | flags | resource_versions)`; in v1, `resource_versions` may be empty.

---

## 6) Frontend editor

* Route: `/workspaces/:workspaceId/configs/:configId/editor`
* Left nav mirrors files:

  ```
  Startup
  Run
  Columns
    + Add Column…
  Table
    Transform
    Validators
  Plan
  History
  ```
* Center: Monaco editor (autosave debounce ~1s); PUT uses `If-Match` with current file sha.
* Right: Mapping Preview (scores + winners) and Quick Test (paste values).
* Top bar: **Save • Dry-run • Publish • Revert • Diff**.

---

## 7) Security & guardrails (v1)

* AST checks on save/publish: import allow-list; block `eval/exec`, `socket`, `subprocess`, raw `open`.
* Network/LLM disabled by default; add resource factories later if needed.
* SQLite in WAL mode; `PRAGMA synchronous=NORMAL`; bounded request sizes for code.

---

## 8) Cutover & removal plan

* Remove legacy `/configurations/**` API routes and code paths.
* Update jobs service & API to require `config_version_id`.
* Migrate tests to new endpoints; delete legacy tests.

---

## 9) Success criteria (DoD)

* Create a config → edit draft files → dry-run against a sample XLSX → publish → submit job with `config_version_id` → job runs deterministically.
* Partial unique indexes enforce single draft/published per config.
* ETag saves prevent stomps; stale writes are rejected.
* Legacy APIs removed; new routes visible in `ade routes:backend`.

---

## 10) Future-friendly hooks (not in v1)

* Artifact persistence from `startup.py` (pack by `files_hash`).
* Resource factories and caching (http/llm).
* Diff tooling between versions.
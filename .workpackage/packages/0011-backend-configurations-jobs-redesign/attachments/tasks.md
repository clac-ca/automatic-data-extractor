### `.workpackage/packages/0011-backend-configurations-jobs-redesign/attachments/tasks.md`

# Implementation checklist

Status: `[ ]` todo • `[~]` in progress • `[x]` done

---

## Phase 1 — Schema rewrite (blocking)

- [ ] Overwrite `backend/app/shared/db/migrations/versions/0001_initial_schema.py`:
  - [ ] Add tables: `configs`, `config_versions`, `config_files`.
  - [ ] Add columns on `jobs`: `config_version_id` (FK), `run_key`.
  - [ ] Drop legacy tables: `configurations`, `configuration_script_versions`, `configuration_columns`.
  - [ ] Add partial unique indexes:
        - one draft per config: `status='draft'`
        - one published per config: `status='published'`
  - [ ] Add CHECK constraint on `config_versions.status` in `{'draft','published','deprecated'}`.
- [ ] Run migrations locally; verify SQLite partial unique indexes compile.

**Acceptance:** `ade routes:backend` still works; DB boots with new schema; old tables are gone.

---

## Phase 2 — Models & services

- [ ] Create `backend/app/features/configs/models.py` with SQLAlchemy models for `configs`, `config_versions`, `config_files`.
- [ ] Implement `ConfigService`:
  - [ ] create package, get package, list packages
  - [ ] ensure single draft per config (create if absent)
  - [ ] list versions (with statuses)
  - [ ] publish `{semver, message}`: copy draft → new version; compute `files_hash`
  - [ ] revert: swap `published`/`deprecated` safely
- [ ] Implement `ConfigFileService`:
  - [ ] list/read draft files
  - [ ] create file (scaffold from template)
  - [ ] update file with ETag (`If-Match` sha256 of code)
  - [ ] delete file
  - [ ] recalc `files_hash` after any mutation
- [ ] Implement `ManifestService`:
  - [ ] read/patch manifest JSON (validate paths/ordinals)
  - [ ] update `files_hash` on changes

**Tests:** `backend/tests/services/configs/` covering lifecycle, uniqueness, ETag, manifest validation.

---

## Phase 3 — API (replace legacy /configurations/**)

- [ ] New router: `backend/app/features/configs/router.py`
  - [ ] Packages: `GET/POST /workspaces/:ws/configs`, `GET/DELETE /.../:configId`
  - [ ] Versions: `GET /.../:configId/versions`, `POST /.../:configId/publish`, `POST /.../:configId/revert`
  - [ ] Draft files: `GET/GET by path/POST/PUT/DELETE`
  - [ ] Draft manifest: `GET/PATCH`
  - [ ] Plan & Dry-run: `POST /.../:configId/draft:plan`, `POST /.../:configId/draft:dry-run`
- [ ] Mount router in `backend/app/api/v1/__init__.py`.
- [ ] Remove legacy configurations router; delete dead code.
- [ ] Error mapping:
  - `412` on ETag mismatch
  - `409` on duplicate draft/published
  - `400` on manifest errors

**Tests:** API happy-path + error-path (ETag, manifest validation, conflict).

---

## Phase 4 — Jobs integration

- [ ] Update `JobsService` to **require** `config_version_id` on submit.
- [ ] Compute `run_key = sha256(doc_sha | files_hash | flags | resource_versions)` (resource_versions empty in v1).
- [ ] Ensure job read APIs expose `config_version_id` and `run_key`.
- [ ] Delete legacy references to `configuration_id`.

**Tests:** submit job → runs with chosen version; re-run same doc hits same `run_key`.

---

## Phase 5 — Runner skeleton

- [ ] Add runner module (e.g., `backend/app/features/jobs/runner_v2.py`):
  - [ ] `Extract` XLSX → tables
  - [ ] `run_start` / `run_end` (in-memory session clients if needed)
  - [ ] `Prepare` (per column), `Detect` (score deltas)
  - [ ] `Map` (Hungarian O(n^3), integer-scaled scores)
  - [ ] `Transform` (column → table), `Validate`
  - [ ] Metrics: sheets_scanned, rows_processed, elapsed_ms
- [ ] Wire Dry-run endpoint to runner (uses **draft** files).
- [ ] Wire Jobs execution to runner (uses **published** version files).

**Tests:** small XLSX fixture → stable mapping and transform; tie-break behavior verified.

---

## Phase 6 — Frontend editor

- [ ] New route: `/workspaces/:workspaceId/configs/:configId/editor`
- [ ] Left nav file tree (Startup, Run, Columns [+Add], Table [Transform/Validators], Plan, History)
- [ ] Monaco editor; Save (PUT) with ETag; stale save -> surface 412
- [ ] Add Column wizard: creates file + updates manifest
- [ ] Dry-run view: mapping preview (scores & winners) + logs
- [ ] Publish modal: `{semver, message}`; Revert action
- [ ] Remove legacy configuration screens

**Tests:** basic unit tests + manual QA script (cURL sequence provided below).

---

## Phase 7 — Docs & polish

- [ ] Update README/ADR with new schema & API.
- [ ] Snapshot routes: `ade routes:backend` and frontend routes.
- [ ] CHANGELOG entry.
- [ ] Cleanup dead code/strings.

---

## Quick cURL script (manual sanity)

```bash
# Create config
curl -X POST /api/v1/workspaces/$WS/configs -d '{"slug":"optima","title":"Optima Roster"}' -H 'Content-Type: application/json'

# List draft files
curl /api/v1/workspaces/$WS/configs/$CFG/draft/files

# Create a column
curl -X POST /api/v1/workspaces/$WS/configs/$CFG/draft/files -d '{"path":"columns/postal_code.py"}' -H 'Content-Type: application/json'

# Save file with ETag
ETAG=$(curl /api/v1/workspaces/$WS/configs/$CFG/draft/files/columns/postal_code.py | jq -r .sha256)
curl -X PUT /api/v1/workspaces/$WS/configs/$CFG/draft/files/columns/postal_code.py \
  -H "If-Match: $ETAG" -d '{"code":"# new code here"}' -H 'Content-Type: application/json'

# Dry-run
curl -X POST /api/v1/workspaces/$WS/configs/$CFG/draft:dry-run -d '{"documentId":"DOCID"}' -H 'Content-Type: application/json'

# Publish
curl -X POST /api/v1/workspaces/$WS/configs/$CFG/publish -d '{"semver":"1.0.0","message":"Initial"}' -H 'Content-Type: application/json'

# Submit job with config_version_id
curl -X POST /api/v1/workspaces/$WS/jobs -d '{"config_version_id":"VERID","input_document_id":"DOCID"}' -H 'Content-Type: application/json'
````

---

## Test matrix (minimum)

* **Schema:** partial unique index enforcement (draft/published), status CHECK.
* **Services:** prevent second draft; publish copies files; revert safe.
* **Manifest:** path existence, unique ordinals, required columns honored.
* **Files:** ETag mismatch → 412; hash recalculation updates `files_hash`.
* **Runner:** mapping determinism; Hungarian tie-break; min_score threshold respected.
* **API:** 400 on bad manifest; 409 on duplicate states; 404 on missing file.

---

## Risks & mitigations

* *Risk:* stale write stomping → **ETag required** on PUT.
* *Risk:* accidental dual published versions → **partial unique index** and service guard.
* *Risk:* schema churn → manifest holds UI metadata (no per-column tables).

---

## Parking lot (post-v1)

* Artifact persistence keyed by `files_hash`.
* Resource factories (http/llm) and caching.
* Version diffs; export/import.
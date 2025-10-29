# Config Engine Spec (v0.4)

## 1. Concept
- Each **config** lives at `data/configs/<config_id>/`.
- Configs are folders containing a `manifest.json`, optional hook scripts in the root, `columns/` modules (one per canonical column), and optional docs like `README.md`.
- Workspaces have exactly one `active` config. Only `inactive` configs may be edited. `archived` configs are immutable snapshots.

## 2. Execution Flow
1. `on_job_start` hook(s) gather `jobContext`.
2. **Detect** phase: every column module runs each `detect_*` function against every raw table column and accumulates scores.
3. **Assign**: server greedily matches canonical columns to raw columns when score > 0.
4. **Transform**: assigned column modules run `transform(...)` once to produce canonical values and warnings.
5. `on_after_extract` runs with mapping + warning info.
6. `on_job_end` runs regardless of success.

## 3. Hooks API (keyword-only)
All hooks expose a `run(...)` function that receives identifiers, environment snapshot, resolved paths, and context objects:
```python
def run(*, workspace_id, config_id, job_id, env, paths, inputs) -> dict | None
```
- `paths` includes `config`, `cache`, `job`, `job_input`.
- Return value merges into calling context (`{"jobContext": {...}}` for `on_job_start`).

## 4. Column Module API
- Multiple detectors per module: any callable starting with `detect_`.
- Required transformer: `transform(...)`.
- Detectors receive the candidate column (`header`, `values`, `column_index`) alongside `table` metadata, `job_context`, and `env`. Return shape:
  ```python
  {"scores": {"self": float, "<other_key>": float}}
  ```
  Scores clamp server-side to `[-5.0, 5.0]`.
- `transform` returns `{"values": [...], "warnings": [...]?}` with length equal to table row count.
- Modules can inspect other columns via `table["samples"]` or load `paths["job_input"]` for full data.

## 5. Runtime Environment
The **jobs** feature is responsible for sandboxed execution. When it runs a config:
- Launch `python -I -B` subprocesses with strict rlimits (network disabled unless manifest enables it).
- Build environment variables from baseline safe vars, `manifest.env`, decrypted `manifest.secrets`, and ADE-specific context vars (`ADE_WORKSPACE_ID`, `ADE_COLUMN_KEY`, `ADE_PATH_*`, etc.).
- Pass kwargs as JSON via stdin and expect JSON stdout.
- Call hooks/column scripts with keyword-only arguments; modules may accept only the keys they need.

## 6. Manifest (`manifest.json`, schema v0.4)
- Keys:
  - `env` (plain env vars) & `secrets` (AES-GCM ciphertext blobs).
  - `engine.defaults` for resource limits (timeouts, memory, network flag).
  - `hooks`: ordered arrays of objects `{"script": "<path.py>", "limits": {"timeout_ms": ...}?}`.
  - `columns.order`: canonical order for export.
  - `columns.meta[key].script`: module path backing each canonical column.
- Activation requires manifest validation to pass and paths to exist.

## 7. Validation Rules
- Folder structure must match allowed files (manifest, hooks, `columns/`, optional docs).
- Manifest checks:
  - All referenced paths exist.
  - `columns.order` unique; meta entries align.
- Column modules:
  - ≥1 `detect_*` callable.
  - A callable `transform`.
  - Dry-run on synthetic 2–3 row data to verify return shapes within timeouts.
- Hook modules must expose callable `run`.
- Secrets must remain ciphertext when uploaded.
- Timeout limits must fall within server bounds (ex. 1–300_000 ms).
- Package integrity captured via canonical ZIP SHA-256 (`package_sha256`) for auditing.

## 8. Detect → Assign → Transform Algorithm
1. Server extracts source tables into `paths["job_input"]` (JSON).
2. Run `on_job_start` to build `jobContext`.
3. Detection: for each canonical column `k` and raw column `t.r`, sum scores from every `detect_*`.
4. Assignment: filter positive scores, sort descending, greedily match without conflicts.
5. Transform: invoke `transform` for each assigned pair, ensuring value counts match row totals.
6. Post-processing: run `on_after_extract` and `on_job_end` (best effort).

## 9. Example Templates
`columns/member_id.py` demonstrates layered detectors and a transformer enforcing uppercase IDs.
`on_job_start.py` illustrates returning localized job context derived from environment variables.

## 10. Follow-Up Work
- Replace legacy config schema with folder-based packages.
- Implement validator that discovers `detect_*` + `transform`, and hook it into the jobs runner responsible for sandbox execution.
- Update FastAPI routes to align with new config lifecycle and validation contract.
- Provide editor UX for inactive config editing, dry-run, and activation per workspace.

# Config Packages — Behavior as Code

A **config package** is a versioned folder of Python scripts and a manifest that defines how ADE interprets,
transforms, and validates spreadsheets. Each package lives under
`${ADE_DATA_DIR}/config_packages/<config_id>/`. Once a version is published it becomes immutable; new edits
always create a new published folder.

Config packages are created and managed through the ADE GUI but can be exported or imported across workspaces.
ADE automatically versions each change, allowing you to test configs safely, restore older versions, or promote
a validated config to production.

> **Principles**
>
> * **Explainable** — every decision is scored and traced into a single artifact JSON.
> * **Deterministic** — small, pure functions with bounded inputs.
> * **Portable** — a package is a folder (or zip) you can export/import.
> * **Safe by default** — no file/network access unless explicitly allowed; runtime limits apply.

Config packages keep ADE explainable and deterministic:

- small, human-readable scripts,
- reproducible builds (`prepare once, run many`),
- isolated execution with network disabled by default.

---

## What’s inside a config package

A config is just a folder (or zip). You can export it, store it under version control, and re-import between
environments.

```text
📁 my-config/
├─ manifest.json          # Central manifest: engine settings, target fields, script paths
├─ 📁 columns/            # Column rules: detect → transform (opt) → validate (opt)
│  ├─ <field>.py          # One file per target field you want in the output
│  ├─ member_id.py        # Example
│  ├─ first_name.py       # Example
│  └─ department.py       # Example
├─ 📁 row_types/          # Row rules for Pass 1: Find Tables & Headers
│  ├─ header.py
│  └─ data.py
├─ 📁 hooks/              # Optional extension points around job stages
│  ├─ on_job_start.py
│  ├─ after_mapping.py
│  ├─ after_transform.py
│  └─ after_validate.py
└─ requirements.txt       # (optional) per-package dependencies
```

---

## Layout inside `${ADE_DATA_DIR}`

During development `ADE_DATA_DIR` defaults to `./data`. In production it is usually mounted to shared storage
(for example, Azure Files) so prepares and job artifacts persist across deploys. All package versions live under
`config_packages/` and line up with their prepared runtime under `venvs/`.

```text
${ADE_DATA_DIR}/                                  # Root folder for all ADE state (default: ./data)
├─ config_packages/
│  └─ <config_id>/
│     ├─ manifest.json           # Engine defaults, target fields, script paths
│     ├─ columns/                # Field logic: detect → transform? → validate?
│     │  └─ <field>.py           # e.g., member_id.py, first_name.py
│     ├─ row_types/              # Row detectors for headers and data rows
│     │  ├─ header.py
│     │  └─ data.py
│     ├─ hooks/                  # Optional lifecycle hooks
│     │  ├─ on_job_start.py
│     │  ├─ after_mapping.py
│     │  ├─ after_transform.py
│     │  └─ after_validate.py
│     └─ requirements.txt?       # Optional Python dependencies (pip installed)
│
├─ venvs/
│  └─ <config_id>/               # Prepared virtualenv reused by every job
│     ├─ bin/python
│     └─ ade-build/
│        ├─ snapshot/            # Frozen copy of the package recorded at prepare time
│        ├─ packages.txt         # Exact dependency lock (pip freeze output)
│        ├─ install.log          # Build/install log for troubleshooting
│        └─ build.json           # Metadata (content hash, deps hash, prepared_at)
│
├─ jobs/
│  └─ <job_id>/
│     ├─ inputs/
│     ├─ artifact.json
│     ├─ normalized.xlsx
│     ├─ events.ndjson
│     ├─ run-request.json
│     └─ .venv → ../../venvs/<config_id>/
│
├─ documents/                    # Shared uploads referenced by multiple jobs
│  └─ <document_id>/
│     └─ <filename>.xlsx         # Original file as received
│
├─ db/                           # Application database (SQLite by default)
│  └─ api.sqlite                  # Metadata for configs, jobs, documents, etc.
│
└─ cache/
   └─ pip/                       # pip download/build cache (safe to delete)
```

The files under `config_packages/` are the scripts you author. ADE never mutates them after publish. Every job
imports the **snapshot** inside `venvs/<config_id>/ade-build/` to guarantee determinism even if the package is
edited later. Pip download/build caches sit alongside this tree in `${ADE_DATA_DIR}/cache/pip/` and can be wiped
without touching published packages.

---

## Author → Prepare → Run

1. **Author** a package in the UI (or via draft APIs). You edit `manifest.json`, add column detectors, row
   detectors, and optional hooks. Once ready, you publish — creating `config_packages/<config_id>/`.
2. **Prepare** the package (see below). ADE builds a virtual environment under `venvs/<config_id>/`, installs
   dependencies from `requirements.txt`, and snapshots the scripts into `ade-build/snapshot/`.
3. **Run** jobs. Workers mount `.venv` from `jobs/<job_id>/.venv`, import the frozen snapshot, execute the five
   passes, and write `artifact.json` plus `normalized.xlsx`. No re-install or rebuild happens during run.

Preparing once and reusing the result keeps runtime predictable and safe — **prepare once, run many**.

---

## Prepare

`prepare` is the bridge between authoring and execution. It performs three checks before a package can run:

1. **Manifest validation** — schema + semantic validation against
   `docs/developers/schemas/manifest.v1.0.schema.json`.
2. **Dependency install** — creates `venvs/<config_id>/` and runs `pip install -r requirements.txt` (if present).
3. **Snapshot build** — copies the exact scripts into `ade-build/snapshot/` and records metadata in
   `ade-build/build.json`.

`prepare` is idempotent: ADE skips work when the manifest hash and dependency hash match what was previously
recorded. When either changes, ADE rebuilds and refreshes the snapshot. Jobs scheduled before a new prepare
continue to use their previous snapshot; new runs pick up the latest prepared version.

---

## Scripts and the five passes

Each file in `columns/` describes how to recognize and clean a single target field. ADE executes the following
passes for every table that survives detection:

1. **Find tables & headers** (`row_types/header.py`, `row_types/data.py`)  
   Functions named `detect_*` vote for whether a row looks like a header or data row. Scores combine to identify
   table boundaries and the header row. See [Pass 1](./03-pass-find-tables-and-headers.md).
2. **Map columns to target fields** (`columns/<field>.py`)  
   `detect_*` functions assign scores to candidate columns. Highest score wins the mapping.
   See [Pass 2](./04-pass-map-columns-to-target-fields.md).
3. **Transform values (optional)** (`transform(...)`)  
   Pure functions that receive the extracted values and return normalized data.
   See [Pass 3](./05-pass-transform-values.md).
4. **Validate values (optional)** (`validate(...)`)  
   Emit structured issues for rows that violate your rules. ADE augments them with coordinates and identifiers.
   See [Pass 4](./06-pass-validate-values.md).
5. **Generate normalized workbook**  
   ADE writes the output workbook using your manifest’s field ordering and labels. See
   [Pass 5](./07-pass-generate-normalized-workbook.md).

Each handler receives structured keyword arguments (job metadata, manifest, environment variables) as described
in the pass-specific guides.

---

## Row detection scripts (Pass 1) — find tables & headers

ADE first locates each table and its header row. Your row-type rules score each row as **header** or **data**.
ADE streams a sheet **row-by-row**, calls every `detect_*` function in `row_types/header.py` and
`row_types/data.py`, sums the score deltas, and labels the row. From those labels it infers table ranges (e.g.,
`"B4:G159"`) and the header row.

**Minimal example — header by text density**

```python
# row_types/header.py
def detect_text_density(
    *,
    job_id: str,                      # unique job identifier
    source_file: str,                 # original source file name
    sheet_name: str,                  # spreadsheet tab or sheet name
    row_index: int,                   # 1-based row index
    row_values_sample: list,          # values in this row
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    artifact: dict,                   # current job artifact (read-only snapshot)
    **_,
) -> dict:
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    textish   = sum(1 for c in non_blank if isinstance(c, str))
    ratio     = textish / max(1, len(non_blank))
    return {"scores": {"header": +0.6 if ratio >= 0.7 else 0.0}}
```

> **No clear header?** If convincing data appears before any header, ADE may promote the previous row. If there’s
> none, it creates a synthetic header (`"Column 1"...`) so the next pass can continue.

---

## Column scripts (Pass 2–4) — map → transform (opt) → validate (opt)

After ADE knows where the table is, it turns to **columns**. Each file in `columns/` represents a **target
field** you want in the normalized output (e.g., `member_id`, `first_name`).

### Pass 2 — Map Columns to Target Fields

Detectors answer: “Does this raw column look like **this** field?” ADE runs your `detect_*` functions and totals
their scores. Highest total wins.

**Minimal detector — match header synonyms**

This detector checks whether the spreadsheet’s header contains any of the known synonyms defined in your config
manifest.

```python
# columns/<field>.py
def detect_synonyms(
    *,
    job_id: str,                      # unique job identifier
    source_file: str,                 # original source file name
    sheet_name: str,                  # current spreadsheet tab or sheet name
    table_id: str,                    # table identifier within sheet
    column_index: int,                # 1-based column index within the table
    header: str | None,               # cleaned column header text
    values_sample: list,              # small sample of column values
    field_name: str,                  # target field name (e.g., first_name)
    field_meta: dict,                 # manifest.columns.meta[field_name]
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    artifact: dict,                   # current job artifact (read-only snapshot)
    **_,
) -> dict:
    """
    Compare the column header against this field’s known synonyms
    from the config manifest. Each match boosts the score.
    """
    score = 0.0
    if header:
        h = header.lower()
        for word in field_meta.get("synonyms", []):
            if word in h:
                score += 0.6
    return {"scores": {field_name: score}}
```

**Detector using values — quick email pattern**

```python
import re

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

def detect_email_shape(
    *,
    job_id: str,
    source_file: str,
    sheet_name: str,
    table_id: str,
    column_index: int,
    header: str | None,
    values_sample: list,
    field_name: str,
    field_meta: dict,
    manifest: dict,
    env: dict | None = None,
    artifact: dict,
    **_,
) -> dict:
    hits  = sum(bool(EMAIL.match(str(v))) for v in values_sample if v)
    ratio = hits / max(1, len(values_sample))
    return {"scores": {field_name: round(ratio, 2)}}
```

> **Ties/unmapped:** If two fields tie or confidence is too low, ADE can leave the column **unmapped** for later
> review. Unmapped columns can be appended to the right of the output (`raw_<header>`) depending on your manifest
> setting.

**Scoring conventions (recommended)**

* Keep individual detector deltas roughly in **[-1.0, +1.0]**; totals act like a confidence signal.
* Use a global confidence gate via `engine.defaults.mapping_score_threshold` (see manifest below). If the best
  score is below the gate, leave the column **unmapped** (safer than guessing).

---

### Pass 3 — Transform Values (optional)

Clean or reshape values for a mapped field (e.g., strip symbols, parse dates). Transforms run column-wise under
the hood while ADE writes rows.

**Minimal transform — normalize IDs**

```python
def transform(*, values, **context):
    """Normalize IDs."""
    def clean(value):
        if value is None:
            return None
        alnum = "".join(ch for ch in str(value) if ch.isalnum()).upper()
        return alnum or None

    return {"values": [clean(v) for v in values], "warnings": []}
```

> **Context:** ADE also supplies `header`, `column_index`, `table_id`, `job_id`, `manifest`, `env`, and
> `artifact`. Accept `**context` (or explicit keyword-only params) to opt into what you need; only `values` is
> required.

---

### Pass 4 — Validate Values (optional)

Flag problems without changing data (e.g., required missing, pattern mismatch). ADE records issues with precise
locations in the artifact.

**Minimal validate — required field**

```python
def validate(
    *,
    job_id: str,
    source_file: str,
    sheet_name: str,
    table_id: str,
    column_index: int,
    header: str | None,
    values: list,
    field_name: str,
    field_meta: dict,
    manifest: dict,
    env: dict | None = None,
    artifact: dict,
    **_,
):
    """Validate required and pattern rules."""
    issues = []
    required = field_meta.get("required", False)
    for i, v in enumerate(values, start=1):
        if required and not v:
            issues.append({
                "row_index": i,
                "code": "required_missing",
                "severity": "error",
                "message": f"{field_name} is required."
            })
    return {"issues": issues}
```

> **Suggested standard issue codes:** `required_missing`, `pattern_mismatch`, `invalid_format`, `out_of_range`,
> `duplicate_value`. Use consistent codes and severities so dashboards can group them reliably.

---

## How scripts receive inputs (so you never touch files)

ADE does the reading and state-tracking. Your functions get **only what they need** and return a small result.
They **do not** open files or mutate state.

**What ADE passes in (common kwargs):**

* **Identifiers** — `job_id`, `source_file`, `sheet_name`, `table_id`, `column_index`
* **Data** — `header`, `values_sample` (detectors) or full `values` (transform/validate)
* **Config** — `manifest`, `env`, and the field’s own `field_name`, `field_meta`
* **Artifact (read-only)** — snapshot of ADE’s running journal (`artifact`) you can consult but not change

**Tiny pattern — use kwargs, ignore the rest safely**

```python
def detect_numeric_hint(*, values_sample: list, field_name: str, **_):
    ratio = sum(str(v).isdigit() for v in values_sample) / max(1, len(values_sample))
    return {"scores": {field_name: 0.4 if ratio > 0.8 else -0.2}}
```

> **Read-only artifact:** treat `artifact` like a reference book (for example, to check which row was marked as
> the header). ADE appends traces and results for you.

---

## Safety and determinism

- Published packages are immutable; jobs always run against the snapshot captured during prepare.
- Workers execute packages inside sandboxed subprocesses with network disabled unless
  `runtime_network_access` is set on the job.
- Structured logging only: `artifact.json` captures decisions, not raw cell values.
- Dependencies are pinned per package via `venvs/<config_id>/ade-build/packages.txt`, so replaying a job is
  deterministic.

---

## The manifest (the essentials)

Your `manifest.json` defines engine defaults, output behavior, and the **target fields** (normalized columns)
with their labels and scripts.

```json
{
  "config_script_api_version": "1",
  "info": { "schema": "ade.manifest/v1.0", "title": "Membership Rules", "version": "1.2.0" },
  "engine": {
    "defaults": {
      "timeout_ms": 120000,
      "memory_mb": 256,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.0
    },
    "writer": { "mode": "row_streaming", "append_unmapped_columns": true, "unmapped_prefix": "raw_" }
  },
  "env": { "LOCALE": "en-CA" },
  "hooks": {
    "on_job_start":   [{ "script": "hooks/on_job_start.py" }],
    "after_mapping":  [{ "script": "hooks/after_mapping.py" }],
    "after_transform":[{ "script": "hooks/after_transform.py" }],
    "after_validate": [{ "script": "hooks/after_validate.py" }]
  },
  "columns": {
    "order": ["member_id", "first_name", "department"],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "required": true,
        "script": "columns/member_id.py",
        "synonyms": ["member id","member#","id (member)"],
        "type_hint": "string"
      },
      "first_name": {
        "label": "First Name",
        "required": true,
        "script": "columns/first_name.py",
        "synonyms": ["first name","given name"],
        "type_hint": "string"
      },
      "department": {
        "label": "Department",
        "required": false,
        "script": "columns/department.py",
        "synonyms": ["dept","division"],
        "type_hint": "string"
      }
    }
  }
}
```

**A few rules of thumb**

* `config_script_api_version` locks the script contract. Use `"1"` unless a migration guide tells you otherwise.
* `columns.order` is the **output order** of target fields.
* `label` values become **output headers** in the normalized sheet.
* Keep `columns.order` and `columns.meta` **in sync** (same field keys).
* Use `type_hint` / `synonyms` / `pattern` to guide detectors and validators (optional but helpful).
* Use `mapping_score_threshold` to avoid low-confidence auto-maps (default `0.0` preserves current behavior).

> **Manifest validation:** ADE validates `manifest.json` against the current schema (`ade.manifest/v1.0`) and
> script API version (`"config_script_api_version": "1"`). Older manifests require migration before ADE will prepare them.

---

## Hooks (optional extensions)

Hooks are small scripts that run at predictable points with the same structured context (including read-only
`artifact`).

| Hook file            | When it runs                    | Good for…                        |
| -------------------- | ------------------------------- | -------------------------------- |
| `on_job_start.py`    | Before ADE begins processing    | Warming caches, logging metadata |
| `after_mapping.py`   | After Pass 2 (Map Columns)      | Inspecting or adjusting mapping  |
| `after_transform.py` | After Pass 3 (Transform Values) | Summaries, downstream triggers   |
| `after_validate.py`  | After Pass 4 (Validate Values)  | Aggregating issues, dashboards   |

**Minimal hook**

```python
# hooks/after_validate.py
def run(*, artifact: dict, **_):
    errors = sum(
        len(t.get("validation", {}).get("issues", []))
        for s in artifact.get("sheets", [])
        for t in s.get("tables", [])
    )
    return {"notes": f"Total issues: {errors}"}
```

> **Cross-field checks:** If you need multi-column rules (for example, `start_date <= end_date`), implement them
> in `after_validate.py`. Keep them deterministic and light. If they produce structured `issues`, ADE merges them
> into the artifact just like per-field results.

---

## Dependencies (optional)

If your rules need third-party libraries:

* Add a **`requirements.txt`** to the package. ADE installs it during prepare into a per-version virtualenv
  (`${ADE_DATA_DIR}/venvs/<config_id>` by default).
* Prefer **pinned versions**. Vendored pure-Python code (`vendor/`) still works when you need to ship deps
  without hitting PyPI.
* If you have one-time setup tasks (for example, downloading ML models into the package folder), perform them
  during your prepare pipeline or in runtime hooks; the prepared snapshot is read-only once jobs start.

> Prepare snapshots live under `venvs/<config_id>/ade-build/` and include `packages.txt`, `install.log`, and
> `build.json` for troubleshooting and audit.

---

## Lifecycle & versioning (UI-first)

Each workspace can keep many configs, but only **one is active**. Others are editable **drafts** or read-only
**archives**.

| Status   | Meaning                          | Editable? | Transition               |
| -------- | -------------------------------- | --------- | ------------------------ |
| draft    | Being authored; not used by jobs | Yes       | → `active`, → `archived` |
| active   | Used by jobs                     | No        | → `archived`             |
| archived | Locked history                   | No        | (clone → new `draft`)    |

**Typical flow**

1. Create a **draft** in the UI.
2. Edit scripts + manifest; test on sample files.
3. **Activate** (becomes read-only; previous active is archived).
4. Export/import as needed (zip) — ADE versions automatically.
5. To roll back, **clone** an archived config, tweak, and activate.

---

## Drafts & file-level editing API

ADE exposes a draft workspace so you can edit manifests and scripts directly from the UI (or any API client)
without round-tripping ZIP uploads.

### Draft lifecycle

1. **Create** a draft from a stored version  
   `POST /api/v1/workspaces/{workspace_id}/configs/{config_id}/drafts`  
   Body: `{"base_config_version_id": "<version_id>"}`  
   Returns draft metadata (ULID, base sequence, timestamps). Drafts are immutable snapshots; the base version
   stays untouched.
2. **List / inspect** drafts  
   `GET .../drafts` → array of drafts for a config  
   `GET .../drafts/{draft_id}` → metadata for a single draft
3. **Browse files** inside the draft package  
   `GET .../drafts/{draft_id}/files` → flat listing of files/directories with `sha256` hashes  
   `GET .../drafts/{draft_id}/files/{path}` → file content (`utf-8`) + current hash
4. **Edit files** with optimistic concurrency  
   `PUT .../drafts/{draft_id}/files/{path}` body:

   ```json
   {
     "content": "new file contents",
     "encoding": "utf-8",
     "expected_sha256": "optional-current-hash"
   }
   ```

   - When `expected_sha256` is provided, the service raises `409 Conflict` if the stored hash differs.  
   - Unsupported (non UTF-8) files return `415 Unsupported Media Type`.  
   - `DELETE .../files/{path}` removes a file or directory if you decide to purge scripts.

5. **Download** a draft as a ZIP  
   `GET .../drafts/{draft_id}/download` streams a canonical archive (matching the layout used for version
   publishing).
6. **Publish** the draft as a new immutable version  
   `POST .../drafts/{draft_id}/publish` body: `{"label": "optional label"}`  
   The service runs the same manifest validation + hashing pipeline used by `POST /versions`, stores a new
   version directory, and keeps the draft for further edits (metadata records the last published version id).

### Access control & notes

- Draft routes require `Workspace.Configs.ReadWrite` (plus CSRF when using session cookies).  
- Hashes (`sha256`) are precomputed server-side to support editor concurrency and quick diffing.  
- Draft metadata lives alongside version directories (`${ADE_DATA_DIR}/config_packages/<config_id>/drafts/<draft_id>/`)
  and survives version publish/garbage-collection.  
- Publishing reuses the same manifest validator (`docs/developers/schemas/manifest.v1.0.schema.json`) and checks
  described above, so scripts stay contract-safe.

Use these endpoints to build a richer editor (manifest form, Monaco for scripts, etc.) without writing zip/unzip
logic client-side.

---

## Contracts (full signatures)

**Conventions (apply to every function):**

* All public functions are **keyword-only** (use `*`) and must tolerate extra kwargs via `**_` for forward
  compatibility.
* ADE passes a **read-only `artifact`** (consult it, don’t mutate it) plus `manifest` and `env`.
* Your function should **never open files** or read spreadsheets directly; ADE streams data for you.
* Return the **small shapes** shown below; ADE records traces and updates the artifact.

---

### Row detectors (Pass 1 — Find Tables & Headers)

Classify the current row (for example, header/data) by returning **score deltas** per row type. ADE aggregates
deltas across all row rules to decide the label and infer table ranges.

```python
def detect_*(
    *,
    job_id: str,                      # unique job identifier
    source_file: str,                 # original source file name
    sheet_name: str,                  # spreadsheet tab or sheet name
    row_index: int,                   # 1-based row index
    row_values_sample: list,          # values in this row
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    artifact: dict,                   # current job artifact (read-only)
    **_,
) -> dict:
    """
    Return shape:
      {"scores": {"header": float, "data": float, ...}}
    Only include non-zero entries. Positive = push toward this type; negative = push away.
    """
```

---

### Column detectors (Pass 2 — Map Columns to Target Fields)

Score how likely the **current raw column** belongs to **this target field**. ADE sums scores from all
`detect_*` in this file and compares totals across fields; highest wins.

```python
def detect_*(
    *,
    job_id: str,                      # unique job identifier
    source_file: str,                 # original source file name
    sheet_name: str,                  # current spreadsheet tab or sheet name
    table_id: str,                    # table identifier within sheet
    column_index: int,                # 1-based column index within the table
    header: str | None,               # cleaned column header text
    values_sample: list,              # small sample of column values
    field_name: str,                  # target field name (e.g., first_name)
    field_meta: dict,                 # manifest.columns.meta[field_name]
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    artifact: dict,                   # current job artifact (read-only)
    **_,
) -> dict:
    """
    Return shape:
      {"scores": {field_name: float}}
    Only include a key for THIS field. Positive increases confidence; negative decreases it.
    """
```

---

### Transform (Pass 3 — Transform Values, optional)

Normalize/clean values for this mapped target field. ADE writes your returned list to the normalized workbook
(row-streaming writer under the hood).

```python
def transform(
    *,
    job_id: str,                      # unique job identifier
    source_file: str,                 # original source file name
    sheet_name: str,                  # spreadsheet tab or sheet name
    table_id: str,                    # e.g., "table_1"
    column_index: int,                # 1-based column index within the table
    header: str | None,               # original source header text
    values: list,                     # full list of values (row order)
    field_name: str,                  # target field name (e.g., "member_id")
    field_meta: dict,                 # manifest.meta[field_name]
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest (e.g., locale)
    artifact: dict,                   # read-only job artifact snapshot
    **_,
) -> dict:
    """
    Return shape:
      {"values": list, "warnings": list[str]}
    - 'values' must be the same length as the input 'values'.
    - 'warnings' is an optional per-column summary (not per-row).
    """
```

---

### Validate (Pass 4 — Validate Values, optional)

Check values without changing them. Report problems; ADE records exact locations in the artifact. Keep checks
deterministic and bounded.

```python
def validate(
    *,
    job_id: str,                      # unique job identifier
    source_file: str,                 # original source file name or path
    sheet_name: str,                  # spreadsheet tab or sheet name
    table_id: str,                    # e.g., "table_1"
    column_index: int,                # 1-based column index within the table
    header: str | None,               # original source header text
    values: list,                     # full list of values for this mapped column (after transform)
    field_name: str,                  # target field name
    field_meta: dict,                 # manifest meta for this field
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    artifact: dict,                   # current job artifact snapshot (read-only)
    **_,
) -> dict:
    """
    Return shape:
      {"issues": [
        {
          "row_index": int,                    # 1-based row index in the table
          "code": "str",                       # stable machine-readable code
          "severity": "error" | "warning" | "info",
          "message": "human-readable message"
        },
        ...
      ]}
    """
```

> **Notes:**  
> - Return `row_index` (1-based within the table); ADE automatically adds Excel-style `a1` coordinates and rule
>   IDs in the artifact.  
> - ADE normalizes common aliases (for example, `missing` → `required_missing`) before persisting issues.

---

### Hooks (optional extension points)

Hooks run with the same structured context (including read-only `artifact`). Return `None` or a small dict (for
example, `{"notes": "text"}`) to annotate the artifact history.

```python
# runs once before the job starts
def run(
    *,
    artifact: dict,                   # read-only artifact (empty or near-empty at this point)
    manifest: dict,                   # parsed manifest.json
    env: dict | None = None,          # environment values from manifest
    job_id: str,                      # job identifier
    source_file: str,                 # original file path/name
    **_
) -> dict | None:
    """
    Hook return shape (optional):
      {"notes": "short message for audit trail"}
    """
```

The same signature applies to `after_mapping.py`, `after_transform.py`, and `after_validate.py`; the only
difference is **when** they run and what’s already present in `artifact`.

---

## What to read next

- How a job runs your config: [Job Orchestration](./02-job-orchestration.md)
- Big-picture, pass-by-pass story with artifact snippets: [Developer Guide](./README.md)
- Deep dives (one page per pass):
  - [Pass 1 — Find tables & headers](./03-pass-find-tables-and-headers.md)
  - [Pass 2 — Map columns](./04-pass-map-columns-to-target-fields.md)
  - [Pass 3 — Transform values](./05-pass-transform-values.md)
  - [Pass 4 — Validate values](./06-pass-validate-values.md)
  - [Pass 5 — Generate normalized workbook](./07-pass-generate-normalized-workbook.md)
- [Artifact Reference](./14-job_artifact_json.md) — understanding the per-job audit trail.

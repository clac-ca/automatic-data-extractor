# Config Packages — Behavior as Code

A **config package** is a versioned folder of Python scripts and a manifest that defines how ADE interprets, transforms, and validates spreadsheets.

Config packages are created and managed through the ADE GUI but can be exported or imported across workspaces. ADE automatically versions each change, allowing you to test configs safely, restore older versions, or promote a validated config to production.

---

## What’s inside a config package

A config is just a folder (or zip). You can export and store it under version control or export/import between environments.

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
└─ 📁 resources/          # Optional lookups/dictionaries for your rules (no secrets)
```

**How the parts line up with the passes**

* **Pass 1 — Find Tables & Headers (Row Detection)** → `row_types/*.py`
* **Pass 2 — Map Columns to Target Fields** → `columns/<field>.py: detect_*`
* **Pass 3 — Transform Values (Optional)** → `columns/<field>.py: transform`
* **Pass 4 — Validate Values (Optional)** → `columns/<field>.py: validate`
* **Pass 5 — Generate Normalized Workbook** → ADE writes the final sheet using your order/labels

---

## Row detection scripts (Pass 1) — find tables & headers

ADE first needs to locate each table and its header row. Your row‑type rules help it score each row as **header** or **data**.

ADE streams a sheet **row‑by‑row**, calls every `detect_*` function in `row_types/header.py` and `row_types/data.py`, sums the score deltas, and labels the row. From those labels it infers table ranges (e.g., `"B4:G159"`) and the header row.

**Minimal example — header by text density**

```python
# row_types/header.py
def detect_text_density(
    *,
    row_values_sample: list,
    manifest: dict,
    artifact: dict,
    **_
):
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    textish   = sum(1 for c in non_blank if isinstance(c, str))
    ratio     = textish / max(1, len(non_blank))
    return {"scores": {"header": +0.6 if ratio >= 0.7 else 0.0}}
```

> **No clear header?** If convincing data appears before any header, ADE may promote the previous row. If there’s none, it creates a synthetic header (`"Column 1"...`) so the next pass can continue.

---

## Column scripts (Pass 2–4) — map → transform (opt) → validate (opt)

After ADE knows where the table is, it turns to **columns**. Each file in `columns/` represents a **target field** you want in the normalized output (e.g., `member_id`, `first_name`).

### Pass 2 — Map Columns to Target Fields

Detectors answer: “Does this raw column look like **this** field?” ADE runs your `detect_*` functions and totals their scores. Highest total wins.

**Minimal detector — match header synonyms**
This detector checks whether the spreadsheet’s header contains any of the known synonyms defined in your config manifest.

```python
# columns/<field>.py
def detect_synonyms(
    *,
    header: str | None,
    values_sample: list,
    manifest: dict,
    artifact: dict,
    field_name: str,
    field_meta: dict,
    **_
):
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
    header: str | None,
    values_sample: list,
    manifest: dict,
    artifact: dict,
    field_name: str,
    field_meta: dict,
    **_
):
    hits  = sum(bool(EMAIL.match(str(v))) for v in values_sample if v)
    ratio = hits / max(1, len(values_sample))
    return {"scores": {field_name: round(ratio, 2)}}
```

> **Ties/unmapped:** If two fields tie or confidence is too low, ADE can leave the column **unmapped** for later review. Unmapped columns can be appended to the right of the output (`raw_<header>`) depending on your manifest setting.

### Pass 3 — Transform Values (optional)

Clean or reshape values for a mapped field (e.g., strip symbols, parse dates). Transforms run column‑wise under the hood while ADE writes rows.

**Minimal transform — normalize IDs**

```python
def transform(*, values: list, **_):
    def clean(v):
        if v is None: return None
        s = "".join(ch for ch in str(v) if ch.isalnum()).upper()
        return s or None
    return {"values": [clean(v) for v in values], "warnings": []}
```

### Pass 4 — Validate Values (optional)

Flag problems without changing data (e.g., required missing, pattern mismatch). ADE records issues with precise locations in the artifact.

**Minimal validate — required field**

```python
def validate(*, values: list, manifest: dict, **_):
    issues = []
    required = manifest["columns"]["meta"]["member_id"].get("required", False)
    if required:
        for i, v in enumerate(values, start=1):
            if not v:
                issues.append({
                    "row_index": i,
                    "code": "required_missing",
                    "severity": "error",
                    "message": "Member ID is required."
                })
    return {"issues": issues}
```

---

## How scripts receive inputs (so you never touch files)

ADE does the reading and state‑tracking. Your functions get **only what they need** and return a small result. They **do not** open files or mutate state.

**What ADE passes in (common kwargs):**

* **Data** — `header`, `values_sample` (detectors) or full `values` (transform/validate)
* **Context** — `sheet_name`, `table_id`, `column_index`
* **Config** — `manifest`, `env`, and the field’s own `field_name`, `field_meta`
* **Artifact (read‑only)** — a snapshot of ADE’s running journal (`artifact`) you can consult but not change

**Tiny pattern — use kwargs, ignore the rest safely**

```python
def detect_numeric_hint(*, values_sample: list, field_name: str, **_):
    ratio = sum(str(v).isdigit()) / max(1, len(values_sample))
    return {"scores": {field_name: 0.4 if ratio > 0.8 else -0.2}}
```

> **Read‑only artifact**: treat `artifact` like a reference book (e.g., to check which row was marked as the header). ADE appends traces and results for you.

---

## The manifest (the essentials)

Your `manifest.json` defines engine defaults, output behavior, and the **target fields** (normalized columns) with their labels and scripts.

```json
{
  "info":   { "schema": "ade.manifest/v0.6", "title": "Membership Rules", "version": "1.2.0" },
  "engine": {
    "defaults": { "timeout_ms": 120000, "memory_mb": 256, "allow_net": false },
    "writer":   { "mode": "row_streaming", "append_unmapped_columns": true, "unmapped_prefix": "raw_" }
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
      "member_id":  { "label": "Member ID",  "required": true,  "script": "columns/member_id.py",  "synonyms": ["member id","member#","id (member)"] },
      "first_name": { "label": "First Name", "required": true,  "script": "columns/first_name.py", "synonyms": ["first name","given name"] },
      "department": { "label": "Department", "required": false, "script": "columns/department.py", "synonyms": ["dept","division"] }
    }
  }
}
```

**A few rules of thumb**

* `columns.order` is the **output order** of target fields.
* `label` values become **output headers** in the normalized sheet.
* Keep `columns.order` and `columns.meta` **in sync** (same field keys).
* Prefer dictionaries/files under `resources/` over network calls ( `allow_net` is off by default).

---

## Hooks (optional extensions)

Hooks are small scripts that run at predictable points with the same structured context (including read‑only `artifact`).

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

---

## Lifecycle & versioning (UI‑first)

Each workspace can keep many configs, but only **one is active**. Others are editable **drafts** or read‑only **archives**.

| Status   | Meaning                          | Editable? | Transition               |
| -------- | -------------------------------- | --------- | ------------------------ |
| draft    | Being authored; not used by jobs | Yes       | → `active`, → `archived` |
| active   | Used by jobs                     | No        | → `archived`             |
| archived | Locked history                   | No        | (clone → new `draft`)    |

**Typical flow**

1. Create a **draft** in the UI.
2. Edit scripts + manifest; test on sample files.
3. **Activate** (becomes read‑only; previous active is archived).
4. Export/import as needed (zip) — ADE versions automatically.
5. To roll back, **clone** an archived config, tweak, and activate.

---

## Contracts (full signatures)

**Conventions (apply to every function):**

* All public functions are **keyword‑only** (use `*`) and **must tolerate extra kwargs** via `**_` for forward compatibility.
* ADE passes a **read‑only `artifact`** (consult it, don’t mutate it) plus `manifest` and `env`.
* Your function should **never open files** or read spreadsheets directly; ADE streams data for you.
* Return the **small shapes** shown below; ADE records traces and updates the artifact.

---

### Row detectors (Pass 1 — Find Tables & Headers)

Classify the current row (e.g., header/data) by returning **score deltas** per row type. ADE aggregates deltas across all row rules to decide the label and infer table ranges.

```python
def detect_*(
    *,
    row_values_sample: list,          # sample of cell values in this row (strings/numbers/None)
    row_index: int,                   # 1-based row index in the sheet
    sheet_name: str,                  # human-friendly sheet name
    table_hint: dict | None,          # optional { "range": "B4:G159", ... } if ADE has a current guess
    manifest: dict,                   # parsed manifest.json
    artifact: dict,                   # read-only job artifact (decisions so far)
    env: dict | None = None,          # config-provided environment values
    **_
) -> dict:
    """
    Return shape:
      {"scores": {"header": float, "data": float, "total_row": float, ...}}
    Only include non-zero entries. Positive = push toward this type; negative = push away.
    """
```

---

### Column detectors (Pass 2 — Map Columns to Target Fields)

Score how likely the **current raw column** belongs to **this target field**. ADE sums scores from all `detect_*` in this file and compares totals across fields; highest wins.

```python
def detect_*(
    *,
    header: str | None,               # cleaned source header text for this column, if present
    values_sample: list,              # small sample of values from this column (strings/numbers/None)
    column_index: int,                # 1-based column index within the table
    sheet_name: str,                  # sheet name
    table_id: str,                    # e.g., "table_1"
    field_name: str,                  # target field this module owns (e.g., "member_id")
    field_meta: dict,                 # meta for this field from manifest.columns.meta[field_name]
    manifest: dict,                   # parsed manifest.json
    artifact: dict,                   # read-only job artifact (decisions so far)
    env: dict | None = None,          # config-provided environment values
    **_
) -> dict:
    """
    Return shape:
      {"scores": {field_name: float}}
    Only include a key for THIS field. Positive increases confidence; negative decreases it.
    """
```

---

### Transform (Pass 3 — Transform Values, optional)

Normalize/clean values for this mapped target field. ADE will write your returned list to the normalized workbook (row‑streaming writer under the hood).

```python
def transform(
    *,
    values: list,                     # full list of values for this mapped column (in row order)
    header: str | None,               # original source header text
    column_index: int,                # 1-based column index within the table
    sheet_name: str,                  # sheet name
    table_id: str,                    # e.g., "table_1"
    field_name: str,                  # target field name (e.g., "member_id")
    field_meta: dict,                 # manifest meta for this field
    manifest: dict,                   # parsed manifest.json
    artifact: dict,                   # read-only job artifact
    env: dict | None = None,          # environment values from manifest
    **_
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

Check values without changing them. Report problems; ADE records exact locations in the artifact. Keep checks deterministic and bounded.

```python
def validate(
    *,
    values: list,                     # full list of values for this mapped column (after transform)
    header: str | None,               # original source header text
    column_index: int,                # 1-based column index within the table
    sheet_name: str,                  # sheet name
    table_id: str,                    # e.g., "table_1"
    field_name: str,                  # target field name
    field_meta: dict,                 # manifest meta for this field
    manifest: dict,                   # parsed manifest.json
    artifact: dict,                   # read-only job artifact
    env: dict | None = None,          # environment values from manifest
    **_
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

> **Note:** You return `row_index`; ADE will attach A1 coordinates and rule ids in the artifact.

---

### Hooks (optional extension points)

Hooks run with the same structured context (including read‑only `artifact`). Return `None` or a small dict (e.g., `{"notes": "text"}`) to annotate the artifact history.

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

The same signature applies to `after_mapping.py`, `after_transform.py`, and `after_validate.py` hooks; the only difference is **when** they run and what’s already present in `artifact` when they do.

---

## What to read next

* How a job runs your config: **[02‑job‑orchestration.md](./02-job-orchestration.md)**
* Big‑picture, pass‑by‑pass story with artifact snippets: **README — Multi‑Pass Overview**
* Deep dives (one page per pass):

  * **[03‑pass‑find‑tables‑and‑headers.md](./03-pass-find-tables-and-headers.md)**
  * **[04‑pass‑map‑columns-to-target-fields.md](./04-pass-map-columns-to-target-fields.md)**
  * **[05‑pass‑transform-values.md](./05-pass-transform-values.md)**
  * **[06‑pass‑validate-values.md](./06-pass-validate-values.md)**
  * **[07‑pass‑generate-normalized-workbook.md](./07-pass-generate-normalized-workbook.md)**
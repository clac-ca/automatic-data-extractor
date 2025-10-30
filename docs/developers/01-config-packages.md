# Config Packages — Behavior as Code

A **config package** tells the ADE engine how to **find tables**, **identify columns**, **transform values**, and **flag issues**, all through small, testable Python scripts.

Workspace owners create and manage these config packages directly through the ADE front end.
This approach makes ADE a configurable platform rather than a fixed parser—you can extend its logic and adapt it to your data model without changing any backend code.
Each config package becomes a self-contained, versioned unit that ADE can execute safely and repeatably.

```text
📁 my-config/
├─ manifest.json                      # Central manifest defining engine settings, target fields, and script paths
├─ 📁 columns/                        # Column-level rules for mapping, transforming, and validating data
│  ├─ member_id.py                    # Detects, transforms, and validates Member ID values
│  ├─ first_name.py                   # Handles First Name column logic
│  └─ department.py                   # Handles Department column logic
├─ 📁 row_types/                      # Row-level rules for detecting headers, data rows, and structure
│  ├─ header.py                       # Detects header rows in Pass 1 (Find Tables & Headers)
│  └─ data.py                         # Detects data rows in Pass 1 (Find Tables & Headers)
├─ 📁 hooks/                          # Optional scripts triggered before or after job stages
│  ├─ on_job_start.py                 # Runs once at job start
│  ├─ after_detection.py              # Runs after Pass 2 (Map Columns); useful for reviewing mappings
│  ├─ after_transformation.py         # Runs after Pass 3 (Transform Values); summarize or adjust results
│  └─ after_validation.py             # Runs after Pass 4 (Validate Values); aggregate issues or generate summaries
```

Each part serves a specific role:

* **Row rules** (in `row_types/`) classify rows during **Pass 1 – Find Tables & Headers**.
* **Column rules** (in `columns/`) identify and handle data during **Pass 2 – Map Columns**, with optional **Transform** and **Validate** logic in later passes.
* **Hooks** (in `hooks/`) let you extend behavior before or after key stages, such as job start or validation.
* **Manifest** (`manifest.json`) ties everything together—defining engine defaults, column order, and script paths.

Each script receives a **read-only view of the artifact JSON** (`artifact`) so it can reference earlier decisions while remaining isolated from other modules.
Each workspace can have exactly **one active config** at a time, while older versions remain as `draft` or `archived` for reference or rollback.

---

## Why config packages matter

Config packages make ADE configurable and scalable by design.
They allow workspace owners to adapt data-parsing logic to their own needs without needing to modify the backend code.

* **Behavior as code** – Logic for detection, transformation, and validation lives in versioned source files that can be reviewed and tested like any other code.
* **Self-service extensibility** – Workspace owners use the front end to build or update configs, empowering domain experts without backend changes.
* **Portability** – Each package is self-contained and can be shared, exported/imported, and reused across environments.
* **Determinism** – Every job records the exact config version and rule hashes in its artifact, ensuring outputs are reproducible and auditable.

---

## Lifecycle

A workspace can hold many configs, but only one is **active**. All others are **draft** (editable) or **archived** (read‑only).

| Status   | Meaning                               | Editable? | Transitions                      |
| -------- | ------------------------------------- | --------- | -------------------------------- |
| draft    | Being authored; not used by jobs      | Yes       | → `active`, → `archived`         |
| active   | The configuration jobs will use       | No        | → `archived` (on replace/retire) |
| archived | Locked record of a past configuration | No        | (clone to create a new draft)    |

Typical flow: **create draft → edit/validate → activate → archive old active**. To roll back, **clone** an archived config to a new draft and activate it.

---

## Manifest (schema v0.6) — what goes in `manifest.json`

The manifest declares config metadata, engine defaults, and **target fields** (the normalized output columns) with their labels and scripts. It also sets writer behavior (e.g., whether to append unmapped columns).

**Manifest (illustrative excerpt):**

```json
{
  "info": {
    "schema": "ade.manifest/v0.6",
    "title": "Membership Rules",
    "version": "1.2.0",
    "description": "Detectors and transforms for member data."
  },
  "engine": {
    "defaults": {
      "timeout_ms": 120000,
      "memory_mb": 256,
      "allow_net": false
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
  },
  "env": { "LOCALE": "en-CA" },
  "secrets": {},
  "hooks": {
    "on_job_start":        [{ "script": "hooks/on_job_start.py" }],
    "after_detection":     [{ "script": "hooks/after_detection.py" }],
    "after_transformation":[{ "script": "hooks/after_transformation.py" }],
    "after_validation":    [{ "script": "hooks/after_validation.py" }]
  },
  "columns": {
    "order": ["member_id", "first_name", "department"],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "required": true,
        "enabled": true,
        "script": "columns/member_id.py",
        "synonyms": ["member id", "member#", "id (member)"]
      },
      "first_name": {
        "label": "First Name",
        "required": true,
        "enabled": true,
        "script": "columns/first_name.py",
        "synonyms": ["first name", "given name"]
      },
      "department": {
        "label": "Department",
        "required": false,
        "enabled": true,
        "script": "columns/department.py",
        "synonyms": ["dept", "division"]
      }
    }
  }
}
```

**Key fields**

* `engine.defaults` — time/memory/network caps for sandboxed script execution.
* `engine.writer` — normalized output writer settings.
* `columns.order` — the output column order for the normalized sheet.
* `columns.meta` — per **target field**: output label, whether required, the module path, and useful synonyms (for detection).

> **Schema links:** See `docs/developers/schemas/manifest.v0.6.schema.json` for the authoritative JSON Schema.

---

## Row‑type modules (`row_types/`) — structure detection

**What they do**
Row‑type modules classify rows during **Pass 1 — Find Tables & Headers**. Each file focuses on one row class (e.g., `header`, `data`). You can expose multiple `detect_*` functions per module; each function contributes score adjustments for its class.

**Contract (row‑type detectors)**

```python
# row_types/header.py
def detect_text_density(*, row_values_sample: list, row_index: int, sheet_name: str,
                        table_hint: dict | None, manifest: dict, artifact: dict,
                        env: dict | None = None, **_) -> dict:
    """
    Return score adjustments for row classes. 'artifact' is read-only.
    """
    # ... compute ratios, etc.
    return { "scores": { "header": +0.6 } }  # only non-zero deltas need be returned
```

**Common parameters**

* `row_values_sample` — a small sample from the row (never full sheet).
* `row_index`, `sheet_name` — location context.
* `table_hint` — optional current bounds guess, if any.
* `manifest` — the parsed manifest JSON.
* `artifact` — **read‑only** current artifact state (rules can consult prior decisions).
* `env` — small key/value context from the manifest.

**Return shape**
`{"scores": {"header": float, "data": float, ...}}` (omit zero entries). The runtime aggregates scores across all row rules to classify rows and infer table ranges. If a strong `data` signal appears before a header, the previous row may be promoted to header; if none, ADE synthesizes “Column 1…N”.

---

## Column modules (`columns/`) — mapping, transform, validate

**What they do**
Column modules attach to **target fields**. Each file can provide:

* One or more `detect_*` functions (**Pass 2 — Map Columns**).
* An optional `transform(values)` (**Pass 3 — Transform Values**).
* An optional `validate(values)` (**Pass 4 — Validate Values**).

**Detector (column)**

```python
# columns/member_id.py
def detect_synonyms(*, header: str | None, values_sample: list, column_index: int,
                    sheet_name: str, table_id: str, manifest: dict, artifact: dict,
                    env: dict | None = None, **_) -> dict:
    """
    Score how likely this raw column is the 'member_id' target field.
    """
    score = 0.0
    if header:
        h = header.lower()
        for syn in manifest["columns"]["meta"]["member_id"].get("synonyms", []):
            if syn in h:
                score += 0.6
    return { "scores": { "member_id": score } }
```

**Transform (optional)**

```python
def transform(*, values: list, header: str | None, column_index: int,
              manifest: dict, artifact: dict, env: dict | None = None, **_) -> dict:
    def clean(v):
        if v is None: return None
        v = "".join(ch for ch in str(v) if ch.isalnum())
        return v.upper()
    out = [clean(v) for v in values]
    return { "values": out, "warnings": [] }  # warnings are per-column summaries
```

**Validate (optional)**

```python
def validate(*, values: list, header: str | None, column_index: int,
             manifest: dict, artifact: dict, env: dict | None = None, **_) -> dict:
    issues = []
    for i, v in enumerate(values, start=1):
        if v is None and manifest["columns"]["meta"]["member_id"].get("required"):
            issues.append({
                "row_index": i,
                "code": "required_missing",
                "severity": "error",
                "message": "Member ID is required."
            })
    return { "issues": issues }
```

**Notes**

* Detectors operate on **samples**; transforms/validators receive **full column values** (streamed by the engine—never all columns at once).
* All functions receive `artifact` **read‑only** so rules can consult earlier decisions (e.g., found headers, current mapping).
* Return shapes are small and deterministic; the engine appends traces/metrics to the artifact.

---

## Hooks (optional)

**Hooks** are optional scripts that run at specific points in the pipeline.
They allow workspace owners to extend ADE’s behavior beyond the standard passes — for example, by adding custom business logic, calling an external service, or performing a final post-processing step.

Each hook file exports a `run(**kwargs)` function that receives the same structured context used by other modules, including a **read-only `artifact`**.
This makes hooks safe, composable, and fully aware of what happened in earlier stages.

You can think of hooks as **extension points**: they let you build on ADE without modifying the engine itself.

| Hook file                 | When it runs                                                                       | Common use cases                                                                                                          |
| ------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `on_job_start.py`         | Before ADE begins processing a job                                                 | Initialize job-level state, preload resources, or log metadata.                                                           |
| `after_detection.py`      | After **Pass 2 – Map Columns**                                                     | Inspect or adjust mappings, run custom validation on detected structures.                                                 |
| `after_transformation.py` | After **Pass 3 – Transform Values**                                                | Summarize column-level changes or trigger downstream automation.                                                          |
| `after_validation.py`     | After **Pass 4 – Validate Values**, right before ADE generates the output workbook | Perform final actions, such as reaching out to external APIs, enriching data, or updating the spreadsheet as a last step. |

For example, an `after_validation.py` hook could read validation results from the `artifact`, query an external system for missing information, and update the output dataset before ADE writes the final workbook.
This makes hooks a flexible and powerful way to add domain-specific extensions without touching the backend code.

---

## Rule IDs & tracing (how matches show up in the artifact)

ADE builds a **rule registry** at job start (stored in the artifact). Examples:

* **Row rules** → `row.header.detect_text_density` → `row_types/header.py:detect_text_density`
* **Column rules** → `col.member_id.detect_synonyms` → `columns/member_id.py:detect_synonyms`
* **Transform** → `transform.member_id` → `columns/member_id.py:transform`
* **Validate** → `validate.member_id` → `columns/member_id.py:validate`

When a rule contributes a non‑zero delta or executes, the artifact records **only the rule ID and numeric effect**, keeping the artifact compact and readable. The registry also includes a short content hash for each implementation so you can prove exactly which code ran.

---

## Local‑first editing & validation (developer UX)

You can author configs entirely in the browser, then **commit a zip** as a draft or active version:

* **L1 (client)** — JSON Schema checks for `manifest.json`, folder/index shape, quick path rules.
* **L2 (client)** — static Python checks (syntax, required functions, signatures) via Tree‑sitter/Pyodide.
* **L3 (server, authoritative)** — sandboxed import + signatures + tiny dry‑runs; builds the **rule registry** included in the artifact.

“Export” downloads the same zip. “Commit” uploads for L3 acceptance and activation.

---

## Contracts (full signatures)

All public functions use **keyword‑only** parameters (order‑insensitive, explicit) and **must** tolerate extra `**_` keys for forward compatibility.

**Row detector**

```python
def detect_*(*, row_values_sample: list, row_index: int, sheet_name: str,
             table_hint: dict | None, manifest: dict, artifact: dict,
             env: dict | None = None, **_) -> dict  # {"scores": {...}}
```

**Column detector**

```python
def detect_*(*, header: str | None, values_sample: list, column_index: int,
             sheet_name: str, table_id: str, manifest: dict, artifact: dict,
             env: dict | None = None, **_) -> dict  # {"scores": {"<target_field>": float}}
```

**Transform**

```python
def transform(*, values: list, header: str | None, column_index: int,
              manifest: dict, artifact: dict, env: dict | None = None, **_) -> dict
# -> {"values": list, "warnings": list[str]}
```

**Validate**

```python
def validate(*, values: list, header: str | None, column_index: int,
             manifest: dict, artifact: dict, env: dict | None = None, **_) -> dict
# -> {"issues": [{"row_index": int, "code": str, "severity": "error"|"warning",
#                 "message": str}]}
```

> **Do not mutate `artifact`** inside rules. The engine updates the artifact and attaches your rule’s trace automatically.

---

## Performance & safety guidelines

* **Keep detectors cheap** — operate on samples only; avoid full scans and heavy regex backtracking.
* **Be pure** — detectors/transform/validate should not perform I/O unless explicitly allowed (`allow_net: true`); prefer `resources/` lookups.
* **Bounded complexity** — prefer O(n) per column; avoid nested row×pattern loops when vectorization can help.
* **Sandboxed** — the runtime enforces memory/time limits and blocks disallowed imports.

---

## Minimal examples (≤30 lines)

**`row_types/header.py`**

```python
def detect_text_density(*, row_values_sample, **_):
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    textish = sum(1 for c in non_blank if isinstance(c, str))
    ratio = (textish / max(1, len(non_blank)))
    return {"scores": {"header": +0.6 if ratio >= 0.7 else 0.0}}

def detect_synonyms(*, row_values_sample, manifest, **_):
    syns = set()
    for meta in manifest["columns"]["meta"].values():
        syns |= set(meta.get("synonyms", []))
    text = " ".join(str(c).lower() for c in row_values_sample if isinstance(c, str))
    hit = any(s in text for s in syns)
    return {"scores": {"header": +0.4 if hit else 0.0}}
```

**`columns/member_id.py`**

```python
def detect_pattern(*, values_sample, **_):
    import re
    pat = re.compile(r"^[A-Za-z0-9]{6,32}$")
    hits = sum(1 for v in values_sample if v and pat.match(str(v)))
    score = min(1.0, hits / max(1, len(values_sample)))  # 0..1
    return {"scores": {"member_id": score}}

def transform(*, values, **_):
    cleaned = []
    for v in values:
        if v is None:
            cleaned.append(None); continue
        s = "".join(ch for ch in str(v) if ch.isalnum()).upper()
        cleaned.append(s or None)
    return {"values": cleaned, "warnings": []}

def validate(*, values, manifest, **_):
    issues = []
    required = manifest["columns"]["meta"]["member_id"].get("required", False)
    for i, v in enumerate(values, start=1):
        if required and not v:
            issues.append({"row_index": i, "code": "required_missing",
                           "severity": "error", "message": "Member ID is required."})
    return {"issues": issues}
```

---

## Notes & pitfalls

* Keep `columns.order` and `columns.meta` keys **in sync**; mismatches confuse mapping and the UI.
* Use clear, inclusive labels (`label`) for output headers (they appear in the normalized file).
* Put reusable dictionaries under `resources/` and warm them in `on_job_start.py` if needed.
* Don’t include plaintext secrets anywhere; use `secrets` and the sandbox will decrypt at runtime.
* Bump `info.version` when behavior changes; the job artifact records rule hashes and file versions.

---

## What’s next

* Learn the end‑to‑end flow in **[02‑job‑orchestration.md](./02-job-orchestration.md)**.
* See how rules are traced in the **artifact JSON** in **README — Multi‑Pass Overview**.
* Review runtime & invocation details in **[05‑pass‑transform‑values.md](./05-pass-transform-values.md)** and **[06‑pass‑validate‑values.md](./06-pass-validate-values.md)**.

---

Previous: [README.md](./README.md)
Next: [02‑job‑orchestration.md](./02-job-orchestration.md)
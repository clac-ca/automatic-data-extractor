# Config Packages — Behavior as Code

A **config package** tells ADE how to recognize tables and columns, how to clean values, and how to flag issues. It’s a portable folder (plus a versioned `manifest.json`) that contains **row-type rules** and **column rules** as small Python modules. Because configs are just files, you can version them, review them, ship them between environments, and activate them without changing application code.

> **At a glance**
>
> - A config is a folder: `manifest.json` + `row_types/` + `columns/` + optional `hooks/` & `resources/`.
> - **Row rules** (e.g., `row_types/header.py`) classify rows in **Pass 1** (structure).
> - **Column rules** (e.g., `columns/member_id.py`) detect/transform/validate in **Pass 2–4**.
> - Scripts receive a **read‑only view of the artifact JSON** (`artifact`) so rules can consult prior decisions.
> - Exactly **one active config per workspace**; others are `draft` or `archived`.

---

## Why configs exist

- **Behavior as code** — keep detection and cleanup logic in reviewed, testable modules.
- **Portability** — copy a folder (or a zip) to share rules across workspaces & environments.
- **Determinism** — every job records the exact config (id + hashes) in its **artifact JSON**.

---

## Lifecycle

A workspace can hold many configs, but only one is **active**. All others are **draft** (editable) or **archived** (read‑only).

| Status   | Meaning                                       | Editable? | Transitions                     |
|----------|-----------------------------------------------|-----------|---------------------------------|
| draft    | Being authored; not used by jobs              | Yes       | → `active`, → `archived`        |
| active   | The configuration jobs will use               | No        | → `archived` (on replace/retire)|
| archived | Locked record of a past configuration         | No        | (clone to create a new draft)   |

Typical flow: **create draft → edit/validate → activate → archive old active**. To roll back, **clone** an archived config to a new draft and activate it.

---

## Folder layout (canonical)

```

my-config/
├─ manifest.json
├─ columns/
│  ├─ member_id.py
│  ├─ first_name.py
│  └─ department.py
├─ row_types/
│  ├─ header.py
│  └─ data.py
├─ hooks/
│  ├─ on_job_start.py
│  ├─ after_detection.py
│  ├─ after_transformation.py
│  └─ after_validation.py
└─ resources/
└─ vendor_aliases.csv

```

> **Notes**
> - We currently ship `row_types/header.py` and `row_types/data.py`. You may add others later (e.g., `total_row.py`) as patterns mature.
> - No raw data lives in a config. Only code, manifest, and optional static resources.

---

## Manifest (schema v0.6) — what goes in `manifest.json`

The manifest declares config metadata, engine defaults, and **target fields** (the normalized output columns) with their labels and scripts.

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
* `columns.meta` — per target field: label, whether required, the rule module path, and useful synonyms.

---

## Row‑type modules (`row_types/`) — structure detection

Row‑type modules classify rows during **Pass 1**. Each file focuses on one row class (e.g., `header`, `data`). You can expose multiple `detect_*` functions per module; each contributes score adjustments for its class.

**Contract (row‑type detectors)**

```python
# row_types/header.py
def detect_text_density(*, row_values_sample: list, row_index: int, sheet_name: str,
                        table_hint: dict | None, manifest: dict, artifact: dict,
                        env: dict | None = None, **_) -> dict:
    """
    Return score adjustments for row classes. artifact is read-only.
    """
    # ... compute ratios, etc.
    return { "scores": { "header": +0.6 } }  # only non-zero deltas need be returned
```

* **Parameters (common):**

  * `row_values_sample` — a small sample from the row (never full sheet).
  * `row_index`, `sheet_name` — location context.
  * `table_hint` — optional current bounds guess, if any.
  * `manifest` — the parsed manifest JSON.
  * `artifact` — **read‑only** current artifact state (so rules can consult prior decisions).
  * `env` — small key/value context (from manifest `env`).
* **Return shape:** `{"scores": {"header": float, "data": float, ...}}`. Omit zero entries.

> The runtime aggregates scores across all row rules to classify rows and infer table ranges. If a strong `data` signal appears before a header, the previous row may be promoted to header; if none, ADE synthesizes “Column 1…N”.

---

## Column modules (`columns/`) — mapping, transform, validate

Column modules attach to **target fields**. Each file can provide:

* One or more `detect_*` functions (for Pass 2 mapping).
* An optional `transform(values)` (for normalization).
* An optional `validate(values)` (for issues).

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

* Detectors operate on **samples**; transforms/validators receive **full column values** (streamed internally, not all columns at once).
* All functions receive `artifact` **read‑only** so rules can consult earlier decisions (e.g., header locations, mapping outcomes for other fields, analyze stats).
* Return shapes are small and deterministic; **the runtime** appends traces/metrics to the artifact.

---

## Hooks (optional)

Hooks run at well‑defined points with a minimal context. Export a `run(**kwargs)` in each scripted hook file.

* `hooks/on_job_start.py` — initialize per‑job state (e.g., seed a lookup cache from `resources/`).
* `hooks/after_detection.py` — observe mapping decisions before transform/validate.
* `hooks/after_transformation.py` — summarize changes.
* `hooks/after_validation.py` — aggregate issues, add job‑level metrics.

All hooks receive `artifact` **read‑only** and may return `{"notes": "..."};` the engine attaches notes to the artifact’s history.

---

## Rule IDs & tracing (how matches show up in the artifact)

ADE builds a **rule registry** at job start (and stores it in the artifact):

* **Row rules** → `row.header.detect_text_density` maps to `row_types/header.py:detect_text_density`
* **Column rules** → `col.member_id.detect_synonyms` maps to `columns/member_id.py:detect_synonyms`
* **Transform** → `transform.member_id` maps to `columns/member_id.py:transform`
* **Validate** → `validate.member_id` maps to `columns/member_id.py:validate`

When a rule contributes a non‑zero delta or executes, the artifact records **only the rule ID and numeric effect**, keeping the artifact compact and readable. The registry also includes a short content hash for each implementation so you can prove exactly which code ran.

---

## Local‑first editing & validation (developer UX)

You can edit configs entirely in the browser and commit a **zip bundle** as a draft or active version:

* **L1 (client)** — JSON Schema checks for `manifest.json`, folder/index shape, quick path rules.
* **L2 (client)** — static Python checks (syntax, required functions, signatures) via Tree‑sitter/Pyodide.
* **L3 (server, authoritative)** — sandboxed import + signatures + tiny dry‑runs; builds the **rule registry** that goes into the artifact.

“Export” simply downloads the same zip. “Commit” uploads it to the server for L3 acceptance and activation.

---

## Contracts (full signatures)

All public functions use **keyword‑only** parameters (order‑insensitive, clear) and **must** tolerate extra `**_` keys for forward compatibility.

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
* **Be pure** — detectors/transform/validate should not perform I/O unless explicitly allowed (`allow_net=true`) and even then, prefer `resources/` lookups.
* **Bounded complexity** — prefer O(n) per column; avoid nested loops over rows × patterns if a vectorized approach works.
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
        if v is None: cleaned.append(None); continue
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

* Keep `columns.order` and `columns.meta` keys **in sync**; mismatches confuse mapping and UI.
* Use clear, inclusive labels (`label`) for output headers (they appear in the normalized file).
* Put reusable dictionaries under `resources/` and load them in memory in `on_job_start.py` if needed.
* Don’t include plaintext secrets anywhere; use `secrets` and the sandbox will decrypt at runtime.
* Version bump (`info.version`) when you change behavior; the job artifact records the exact rule hashes.

---

## What’s next

* Learn the multi‑pass flow in **[02‑jobs‑pipeline.md](./02-jobs-pipeline.md)** (how ADE executes your rules).
* See how rules are traced in the **artifact JSON** in **README (Multi‑Pass Overview)**.
* Review the runtime, sandbox, and invocation order in **[04‑runtime-model.md](./04-runtime-model.md)**.
* Troubleshoot rule outputs in **[06‑validation-and-diagnostics.md](./06-validation-and-diagnostics.md)**.

---

Previous: [README.md](./README.md)
Next: [02-jobs-pipeline.md](./02-jobs-pipeline.md)
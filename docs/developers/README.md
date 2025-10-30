# Developer Guide

Welcome to the **ADE (Automatic Data Extractor)** developer guide.
This is your entry point for understanding **how ADE works**, **what you configure**, and **how to extend behavior** with small, testable Python scripts.

ADE turns messy spreadsheets into a clean, **normalized** workbook through a few focused passes. It reads in a **streaming** way (no full‑sheet loads) and records every decision in a single **artifact JSON** so you can audit what happened and why.

---

## What you’ll learn

* The big picture: **how ADE processes a file** from start to finish
* How to **configure behavior** with a portable **config package**
* How the **artifact JSON** explains every decision
* Where to start to **add a new field** (e.g., detect/clean/validate **SIN**)

> If you’re brand new, read this page top‑to‑bottom. Each section introduces an idea in plain language, then shows a minimal example you can copy.

---

## The big picture (how ADE runs a file)

ADE processes a spreadsheet in small, ordered passes. Each pass **reads** from and **appends** to the same **artifact JSON** (your audit trail).

```
Input workbook
├─ Pass 1: Find tables & headers (row detection)
├─ Pass 2: Map columns → target fields
├─ Pass 3: Transform values (optional)
├─ Pass 4: Validate values (optional)
└─ Pass 5: Generate normalized workbook (row‑streaming writer)
```

* **Streaming I/O**: reads rows/columns without loading entire sheets.
* **Explainable**: rule scores and contributors show why a decision was made.
* **Safe**: the artifact stores locations and decisions, **not raw cell data**.

Deep dive: **[02‑Job Orchestration](./02-job-orchestration.md)**

---

## Core concepts (quick glossary)

* **Config package** — a portable folder that tells ADE how to find tables, map columns, transform, and validate. You create/edit configs in the **web UI** and can export/import them as a **.zip**. ADE versions configs automatically.
* **Target field** — a normalized column you want in the output (e.g., `member_id`, `sin`, `start_date`).
* **Artifact JSON** — a single file ADE builds as it runs; it records structure, mappings, transforms, validations, and output info. Use it for **audit and troubleshooting**.
* **A1 ranges** — ADE uses Excel A1 notation to reference places (e.g., `"B4"`, `"B4:G159"`).

Reference: **[Glossary](./glossary.md)**

---

## Configure behavior with a config package

A config package is a **folder (or zip)** you manage in the UI:

```text
📁 my-config/
├─ manifest.json                  # engine settings, target fields, script paths
├─ columns/                       # column rules: detect → transform (opt) → validate (opt)
│  ├─ member_id.py
│  ├─ first_name.py
│  └─ sin.py                      # (you add this)
├─ row_types/                     # row rules for Pass 1: find tables & headers
│  ├─ header.py
│  └─ data.py
├─ hooks/                         # optional: run around job stages
│  ├─ on_job_start.py
│  ├─ after_mapping.py
│  ├─ after_transform.py
│  └─ after_validate.py
└─ resources/                     # optional lookups for your rules (no secrets)
```

* **Row rules** (`row_types/*.py`) help ADE **find tables & headers**.
* **Column rules** (`columns/<field>.py`) **map**, then optionally **transform** and **validate** one **target field** each.
* **Hooks** let you run custom logic around stages (all receive a **read‑only artifact**).

Details & contracts: **[01‑Config Packages — Behavior as Code](./01-config-packages.md)**

---

## Quick start: add a SIN field (detect → transform → validate)

Goal: teach ADE to recognize a **SIN** column, normalize values, and flag invalid ones.

### 1) Add `columns/sin.py`

```python
# columns/sin.py
import re

_DIGITS = re.compile(r"\d+")
def _only_digits(s): return "".join(_DIGITS.findall(str(s))) if s is not None else ""
def _luhn_ok(d):
    if len(d) != 9 or not d.isdigit(): return False
    total = 0
    for i, ch in enumerate(d):         # positions 1..9
        n = ord(ch) - 48
        if (i + 1) % 2 == 0:           # double even positions
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0

# --- Pass 2: detection ---------------------------------------------------------
def detect_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_):
    score = 0.0
    if header:
        h = header.lower()
        for syn in field_meta.get("synonyms", []):
            if syn.lower() in h:
                score += 0.6
    return {"scores": {field_name: round(score, 2)}}

def detect_value_shape(*, values_sample: list, field_name: str, **_):
    if not values_sample: return {"scores": {field_name: 0.0}}
    total = valid = 0
    for v in values_sample:
        if v in (None, ""): continue
        total += 1
        d = _only_digits(v)
        if len(d) == 9 and _luhn_ok(d): valid += 1
    if total == 0: return {"scores": {field_name: 0.0}}
    ratio = valid / total
    return {"scores": {field_name: 0.9 if ratio >= 0.8 else round(0.5 * ratio, 2)}}

# --- Pass 3: transform (optional) ---------------------------------------------
def transform(*, values: list, **_):
    def fmt(d): return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    out, normalized = [], 0
    for v in values:
        if v in (None, ""): out.append(None); continue
        d = _only_digits(v)
        if len(d) == 9: out.append(fmt(d)); normalized += 1
        else: out.append(v)
    return {"values": out, "warnings": [f"normalized: {normalized}/{len(values)}"]}

# --- Pass 4: validate (optional) ----------------------------------------------
def validate(*, values: list, field_meta: dict, **_):
    issues, required = [], bool(field_meta.get("required"))
    for i, v in enumerate(values, start=1):
        d = _only_digits(v)
        blankish = (v is None) or (str(v).strip() == "")
        if required and blankish:
            issues.append({"row_index": i, "code": "required_missing",
                           "severity": "error", "message": "SIN is required."})
        elif not blankish and (len(d) != 9 or not _luhn_ok(d)):
            issues.append({"row_index": i, "code": "sin_invalid",
                           "severity": "error", "message": "Invalid SIN."})
    return {"issues": issues}
```

### 2) Add it to `manifest.json`

```json
{
  "columns": {
    "order": ["sin", "first_name", "department"],
    "meta": {
      "sin": {
        "label": "SIN",
        "required": true,
        "script": "columns/sin.py",
        "synonyms": ["sin", "social insurance number", "sin number", "social-insurance-number"]
      }
    }
  }
}
```

### 3) Run a job from the UI

* Pick your config (activate a draft if needed).
* Upload a workbook and run. ADE streams the file, applies your rules, then writes `normalized.xlsx`.

### 4) Inspect the artifact (`artifact.json`)

* See **mapping** (which column mapped to `sin` and why)
* See **transform** summary and **validation** issues with **A1** locations

Full artifact reference: **[14‑Job Artifact JSON](./14-job_artifact_json.md)**

---

## The artifact JSON (why you should care)

**During** a run, the artifact lets rules **consult prior decisions** (read‑only).
**After** a run, it is your **audit log** and **debugging tool**.

What you’ll find inside:

* **`rules` registry** — short IDs → `impl` path + content hash
* **`sheets[].tables[]`** — A1 ranges, header descriptor, source headers
* **`mapping[]`** — raw→target assignments, scores, and rule contributors
* **`transforms[]` / `validation`** — change counts, issues with cell locations
* **`output` + `summary`** — where the normalized file was written and basic stats

Minimal example snippet:

```json
{
  "rules": {
    "col.sin.detect_value_shape": { "impl": "columns/sin.py:detect_value_shape", "version": "af31bc" }
  },
  "sheets": [{
    "id": "sheet_1",
    "tables": [{
      "id": "table_1",
      "mapping": [
        {
          "raw": { "column": "col_3", "header": "SIN Number" },
          "target_field": "sin",
          "score": 1.7,
          "contributors": [{ "rule": "col.sin.detect_value_shape", "delta": 0.9 }]
        }
      ]
    }]
  }]
}
```

Full example, schema, and Pydantic models: **[14‑Job Artifact JSON](./14-job_artifact_json.md)**

---

## Development workflow (UI‑first, versioned)

1. **Create a draft config** in the UI (the UI scaffolds your package).
2. **Edit scripts** and `manifest.json` (tests and sample runs encouraged).
3. **Activate** when ready (ADE archives the previously active config).
4. **Export/import** as a `.zip` to share across workspaces.
5. **Roll back** by cloning an archived config to a new draft and re‑activating.

Validation layers:

* **L1 (client)**: Schema + structure checks for the package and manifest
* **L2 (client)**: Static Python checks (syntax & signatures)
* **L3 (server)**: Sandboxed import + tiny dry‑runs; builds the **rule registry** stored in the artifact

Details: **[01‑Config Packages](./01-config-packages.md)**

---

## Troubleshooting with the artifact

* **A column mapped incorrectly** → check `mapping[].contributors[]` to see which rule pushed it.
* **Too many unmapped columns** → add synonyms for missing headers or create new detectors.
* **Transform didn’t run** → verify the module exposes a `transform` function and the field is actually mapped.
* **Validation is noisy** → tune thresholds, split checks into warnings vs. errors, or add a transform first.
* **Header not found** → see `row_classification[]` scores; ADE may synthesize headers if none are clear.

---

## Performance & safety

* Detectors run on **samples**, not full columns; keep them light and deterministic.
* Transforms/validators operate column‑wise while ADE writes rows (streaming writer).
* Runtime is sandboxed with time/memory limits; network is **off** by default (`allow_net: false`).
* Prefer `resources/` lookups to external calls; never embed secrets in code.

---

## Where to go next

* **Config anatomy & contracts** → **[01‑Config Packages](./01-config-packages.md)**
* **Pass‑by‑pass execution** → **[02‑Job Orchestration](./02-job-orchestration.md)**
* **Artifact spec, schema, and models** → **[14‑Job Artifact JSON](./14-job_artifact_json.md)**
* **Glossary** → **[Shared terminology](./glossary.md)**
* **Snippet conventions** → **[templates/snippet-conventions.md](./templates/snippet-conventions.md)**
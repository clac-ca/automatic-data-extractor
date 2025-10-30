# Config Packages — Behavior as Code

A **config package** tells ADE how to **find tables**, **identify columns**, **transform values**, and **flag issues** — all with small, testable Python scripts. Workspace owners create and manage configs in the ADE front end, making ADE a configurable platform rather than a fixed parser. Each config is a self‑contained, versioned unit that ADE can execute safely and repeatably.

> **Why this matters**
>
> * You edit behavior without touching backend code.
> * Rules live alongside a versioned manifest you can review and test.
> * Jobs record the exact config (and rule hashes) they used for deterministic, auditable runs.

---

## What’s inside a config package

A config is just a folder (or zip). You can put it under version control and move it between environments.

```text
📁 my-config/
├─ manifest.json                      # Central manifest: engine settings, target fields, script paths
├─ 📁 columns/                        # Column rules: detect → transform (opt) → validate (opt)
│  ├─ member_id.py
│  ├─ first_name.py
│  └─ department.py
├─ 📁 row_types/                      # Row rules used in Pass 1: Find Tables & Headers
│  ├─ header.py
│  └─ data.py
├─ 📁 hooks/                          # Optional extension points around job stages
│  ├─ on_job_start.py                 # Runs once at job start
│  ├─ after_mapping.py                # After Pass 2: Map Columns to Target Fields
│  ├─ after_transform.py              # After Pass 3: Transform Values
│  └─ after_validate.py               # After Pass 4: Validate Values
└─ 📁 resources/                      # Optional lookups, dictionaries, etc. (no secrets)
   └─ vendor_aliases.csv
```

**How the parts line up with the passes**

* **Pass 1 — Find Tables & Headers (Row Detection)** → `row_types/*.py`
* **Pass 2 — Map Columns to Target Fields** → `columns/<field>.py: detect_*`
* **Pass 3 — Transform Values (Optional)** → `columns/<field>.py: transform`
* **Pass 4 — Validate Values (Optional)** → `columns/<field>.py: validate`
* **Pass 5 — Generate Normalized Workbook** → uses your manifest’s output order/labels

Every script receives a **read‑only view of the artifact JSON** (`artifact`) so it can consult earlier decisions without mutating state.

---

## Lifecycle

A workspace can hold many configs, but only one is **active**. All others are **draft** (editable) or **archived** (read‑only).

| Status   | Meaning                               | Editable? | Transitions                      |
| -------- | ------------------------------------- | --------- | -------------------------------- |
| draft    | Being authored; not used by jobs      | Yes       | → `active`, → `archived`         |
| active   | The configuration jobs will use       | No        | → `archived` (on replace/retire) |
| archived | Locked record of a past configuration | No        | (clone to create a new draft)    |

**Typical flow**: create draft → edit/validate → activate → archive previous active.
**Roll back**: clone an archived config to a new draft and activate it.

---

## The manifest (`manifest.json`, schema v0.6)

The manifest declares config metadata, engine defaults, and **target fields** (the normalized output columns) with their labels and scripts. It also sets writer behavior (e.g., whether to append unmapped columns).

> **Schema:** see `docs/developers/schemas/manifest.v0.6.schema.json` (authoritative).

**Illustrative excerpt**

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

**Key fields to know**

* `engine.defaults` — caps for sandboxed execution (time, memory, network).
* `engine.writer` — normalized output settings (streaming mode, handling unmapped columns).
* `columns.order` — the **output order** of target fields in the normalized sheet.
* `columns.meta` — per **target field**: output label, whether required, script path, and useful synonyms for detection.

---

## Row‑type modules (`row_types/`) — Find Tables & Headers

**What they do**
Classify rows during **Pass 1** (e.g., `header`, `data`). Each module can expose multiple `detect_*` rules; each returns **score deltas** for its class. ADE aggregates deltas to assign the row’s label and infer table ranges.

**Contract (row detector)**

```python
# row_types/header.py
def detect_text_density(*, row_values_sample: list, row_index: int, sheet_name: str,
                        table_hint: dict | None, manifest: dict, artifact: dict,
                        env: dict | None = None, **_) -> dict:
    """
    Return score adjustments for row classes. 'artifact' is read-only.
    """
    # ... compute ratios, etc.
    return {"scores": {"header": +0.6}}  # only non-zero deltas need be returned
```

**Common parameters**

* `row_values_sample` — a small sample from the row (never the full sheet).
* `row_index`, `sheet_name` — location context.
* `table_hint` — optional current bounds guess.
* `manifest` — parsed manifest JSON.
* `artifact` — **read‑only** current artifact state (consult, don’t mutate).
* `env` — small key/value context from the manifest.

**Return shape**
`{"scores": {"header": float, "data": float, ...}}` (omit zeros). If a strong `data` signal appears before a header, ADE may promote the **previous** row as header; if none exists, it synthesizes **“Column 1…N”** headers so mapping can proceed.

> You can add new row types later (e.g., `total_row.py`) as patterns mature.

---

## Column modules (`columns/`) — Map → Transform (opt) → Validate (opt)

**What they do**
Column modules attach to **target fields** and provide:

* One or more `detect_*` functions (**Pass 2 — Map Columns to Target Fields**).
* An optional `transform(values)` (**Pass 3 — Transform Values**).
* An optional `validate(values)` (**Pass 4 — Validate Values**).

**Detector example**

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
    return {"scores": {"member_id": score}}
```

**Transform example (optional)**

```python
def transform(*, values: list, header: str | None, column_index: int,
              manifest: dict, artifact: dict, env: dict | None = None, **_) -> dict:
    def clean(v):
        if v is None: return None
        v = "".join(ch for ch in str(v) if ch.isalnum())
        return v.upper()
    out = [clean(v) for v in values]
    return {"values": out, "warnings": []}  # per-column summary warnings
```

**Validate example (optional)**

```python
def validate(*, values: list, header: str | None, column_index: int,
             manifest: dict, artifact: dict, env: dict | None = None, **_) -> dict:
    issues = []
    required = manifest["columns"]["meta"]["member_id"].get("required", False)
    for i, v in enumerate(values, start=1):
        if required and not v:
            issues.append({
                "row_index": i,
                "code": "required_missing",
                "severity": "error",
                "message": "Member ID is required."
            })
    return {"issues": issues}
```

**Notes**

* Detectors operate on **samples**; transforms/validators receive **full column values** (streamed internally, not all columns at once).
* All functions receive `artifact` **read‑only** so rules can consult earlier decisions (e.g., found headers, current mapping).
* The engine appends traces/metrics to the artifact; your functions return only small, deterministic payloads.

---

## Hooks (optional)

Hooks are extension points with a minimal, structured context (including read‑only `artifact`). Export a `run(**kwargs)` in each file.

| Hook file            | When it runs                                    | Common use cases                                 |
| -------------------- | ----------------------------------------------- | ------------------------------------------------ |
| `on_job_start.py`    | Before ADE begins processing a job              | Warm caches from `resources/`, record metadata   |
| `after_mapping.py`   | After **Pass 2 — Map Columns to Target Fields** | Inspect or adjust mapping decisions              |
| `after_transform.py` | After **Pass 3 — Transform Values**             | Summarize changes, trigger downstream automation |
| `after_validate.py`  | After **Pass 4 — Validate Values**              | Aggregate issues, add job‑level metrics          |

> Hooks let you add domain‑specific behavior without modifying the engine. Keep them pure and quick.

---

## Rule IDs & tracing (how matches appear in the artifact)

ADE builds a **rule registry** at job start and stores it in the artifact. Examples:

* **Row rules** → `row.header.detect_text_density` → `row_types/header.py:detect_text_density`
* **Column rules** → `col.member_id.detect_synonyms` → `columns/member_id.py:detect_synonyms`
* **Transform** → `transform.member_id` → `columns/member_id.py:transform`
* **Validate** → `validate.member_id` → `columns/member_id.py:validate`

Elsewhere in the artifact, ADE records **only the rule ID and its numeric effect** (e.g., `delta` for scores), plus short content hashes in the registry, keeping the artifact compact and auditable.

---

## Local‑first editing & validation (developer UX)

You can author configs entirely in the browser, then **commit a zip** as a draft or activate it.

* **L1 (client):** JSON Schema checks for `manifest.json`, folder shape, path rules.
* **L2 (client):** static Python checks (syntax, required functions, signatures) via Pyodide/Tree‑sitter.
* **L3 (server, authoritative):** sandboxed import + signature checks + tiny dry‑runs; builds the **rule registry** that goes into the artifact.

“Export” downloads the same zip. “Commit” uploads for L3 acceptance and activation.

---

## Contracts (full signatures)

All public functions use **keyword‑only** parameters and must tolerate extra `**_` keys for forward compatibility.

**Row detector**

```python
def detect_*(*, row_values_sample: list, row_index: int, sheet_name: str,
             table_hint: dict | None, manifest: dict, artifact: dict,
             env: dict | None = None, **_) -> dict
# -> {"scores": {"header": float, "data": float, "...": float}}
```

**Column detector**

```python
def detect_*(*, header: str | None, values_sample: list, column_index: int,
             sheet_name: str, table_id: str, manifest: dict, artifact: dict,
             env: dict | None = None, **_) -> dict
# -> {"scores": {"<target_field>": float}}
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
# -> {"issues": [{"row_index": int, "code": str, "severity": "error"|"warning", "message": str}]}
```

> **Do not mutate `artifact`** inside rules. The engine updates the artifact and attaches traces automatically.

---

## Performance & safety guidelines

* **Keep detectors cheap** — operate on samples; avoid full scans and heavy backtracking.
* **Be pure** — no I/O unless `engine.defaults.allow_net` (prefer `resources/` lookups).
* **Bounded complexity** — aim for O(n) per column; prefer vectorization.
* **Sandboxed** — the runtime enforces memory/time limits and blocks disallowed imports.

---

## Minimal examples (≤30 lines)

**`row_types/header.py`**

```python
def detect_text_density(*, row_values_sample, **_):
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    textish = sum(1 for c in non_blank if isinstance(c, str))
    ratio = textish / max(1, len(non_blank))
    return {"scores": {"header": +0.6 if ratio >= 0.7 else 0.0}}

def detect_synonyms(*, row_values_sample, manifest, **_):
    syns = set()
    for meta in manifest["columns"]["meta"].values():
        syns |= set(meta.get("synonyms", []))
    blob = " ".join(str(c).lower() for c in row_values_sample if isinstance(c, str))
    return {"scores": {"header": +0.4 if any(s in blob for s in syns) else 0.0}}
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
    if manifest["columns"]["meta"]["member_id"].get("required", False):
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

## Notes & pitfalls

> **Tip:** Keep `columns.order` and `columns.meta` keys **in sync** — mismatches confuse mapping and the UI.
> **Tip:** Choose clear, inclusive `label`s — they become your **output headers**.
> **Pitfall:** Don’t store secrets in code or resources; use the manifest’s `secrets` (decrypted only in sandboxed child processes).
> **Versioning:** Bump `info.version` when behavior changes; the job artifact records rule hashes and file versions.

---

## What’s next

* Learn the end‑to‑end flow in **[02‑job‑orchestration.md](./02-job-orchestration.md)**.
* See how rules are traced in the **artifact JSON** in the **README — Multi‑Pass Overview**.
* Deep‑dive the passes in:

  * **[03‑pass‑find‑tables‑and‑headers.md](./03-pass-find-tables-and-headers.md)**
  * **[04‑pass‑map‑columns-to-target-fields.md](./04-pass-map-columns-to-target-fields.md)**
  * **[05‑pass‑transform‑values.md](./05-pass-transform-values.md)**
  * **[06‑pass‑validate‑values.md](./06-pass-validate-values.md)**
  * **[07‑pass‑generate-normalized-workbook.md](./07-pass-generate-normalized-workbook.md)**

---

Previous: [README.md](./README.md)
Next: [02‑job‑orchestration.md](./02-job-orchestration.md)
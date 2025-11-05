# Config Packages — Click‑Through Reference (Teaching Edition)



An ADE **config package** is an installable Python distribution that bundles your spreadsheet rules inside **`ade_config`**. ADE builds **one virtual environment per configuration** and reuses it deterministically (**build once, run many**).

> Runtime note: Workers run in standard Python virtual environments. We **do not hard‑block network traffic**; keep rules deterministic, pure, and lightweight. Avoid network calls unless your use case truly requires it.

**Config packages are stored here:** `${ADE_DATA_DIR}/workspaces/<workspace_id>/config_packages/<config_id>/`

**And copied to the virtual env upon build:** `${ADE_DATA_DIR}/workspaces/<workspace_id>/venvs/<config_id>/`

---
<a id="top"></a>

## Clickable file tree (with concise inline comments)

> Click any item to jump to its section. Each file’s code block is written to teach the concept: small, readable functions, realistic inputs/outputs, and comments that explain “why,” not just “what.”

* **my-config/**

  * **[pyproject.toml](#pyproject-toml)** — packaging metadata; ADE installs this into the per‑config venv.
  * **src/**

    * **ade_config/** — runtime package imported by the worker.

      * **[manifest.json](#manifestjson)** — engine defaults, column model (order + meta), hook entrypoints.
      * **[config.env](#configenv-optional)** *(optional)* — environment “knobs” for detectors/transforms (e.g., `DATE_FMT`).
      * **[_shared.py](#sharedpy)** — tiny helpers used across detectors (name‑casing, date/number parsing, ratios).
      * **[column_detectors/](#column_detectors)** — one script **per normalized field**: map → transform → validate.

        * **[member_id.py](#member_idpy)** — IDs (synonyms + regex + uniqueness) → uppercase alphanumerics; duplicates flagged.
        * **[first_name.py](#first_namepy)** — names (shape checks + careful title‑case for O’Neil/McKay/hyphens).
        * **[last_name.py](#last_namepy)** — same approach as first name (consistency matters).
        * **[email.py](#emailpy)** — email pattern + lowercase + gentle domain typo repairs; duplicates flagged.
        * **[department.py](#departmentpy)** — env‑driven synonyms → canonical labels; warn on out‑of‑set.
        * **[join_date.py](#join_datepy)** — Excel serials + flexible formats → ISO `YYYY‑MM‑DD`; future‑date grace window.
        * **[amount.py](#amountpy)** — currency strings → precise `Decimal` rounding → float for Excel writer.
      * **[row_detectors/](#row_detectors)** — vote per row to find tables & header rows (Pass 1).

        * **[header.py](#headerpy)** — text density ↑, early‑row bias ↑, numeric penalty ↓ → headers.
        * **[data.py](#datapy)** — numeric presence ↑, moderate blanks OK, not header‑like → data rows.
      * **[hooks/](#hooks)** — lifecycle extension points (small, fast, deterministic).

        * **[on_job_start.py](#on_job_startpy)** — provenance note + quick env sanity.
        * **[after_mapping.py](#after_mappingpy)** — post‑mapping guidance (suggest synonyms instead of force‑mapping).
        * **[before_save.py](#before_savepy)** — “Summary” sheet; standardized naming; optional freeze/autosize.
        * **[on_job_end.py](#on_job_endpy)** — compact issue breakdown for triage.
      * **[**init**.py](#initpy)** — marks `ade_config` as a package (empty is fine).

---

## pyproject.toml

<a id="pyproject-toml"></a> [↑ back to tree](#top)

```toml
# pyproject.toml — installable package for ADE to build into a venv.

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ade-config-membership"             # Keep stable; bump version when publishing
version = "1.3.1"
description = "ADE configuration: detectors, transforms, validators, hooks"
readme = "README.md"
requires-python = ">=3.11"
authors = [{ name = "Data Quality Team", email = "dq@example.com" }]
license = { text = "Proprietary" }
keywords = ["ade", "etl", "spreadsheets", "validation", "mapping"]

[project.urls]
Homepage = "https://your-company.example/ade/configs/membership"

[tool.setuptools]
package-dir = {"" = "src"}                 # src/ layout

[tool.setuptools.packages.find]
where = ["src"]
include = ["ade_config*"]                  # Only ship the runtime package

[tool.ade]
display_name = "Membership Normalization"
min_engine = ">=0.4.0"
tags = ["membership", "hr", "finance"]
```

---

## src/ade_config/manifest.json

<a id="manifestjson"></a> [↑ back to tree](#top)

> Shown as **JSONC** (JSON with comments). Remove comments in the real file.

```jsonc
{
  "config_script_api_version": "1",

  "info": { "schema": "ade.config-manifest/v1", "title": "Membership Rules", "version": "1.3.1" },

  "engine": {
    "defaults": {
      "timeout_ms": 180000,
      "memory_mb": 384,
      "mapping_score_threshold": 0.35  // if best field score < 0.35 → leave unmapped (safer)
    },
    "writer": { "mode": "row_streaming", "append_unmapped_columns": true, "unmapped_prefix": "raw_" }
  },

  "env": {
    "LOCALE": "en-CA",
    "DATE_FMT": "%Y-%m-%d",
    "AMOUNT_DECIMALS": "2",
    "FUTURE_DATE_GRACE_DAYS": "7",
    "DEPT_CANONICAL": "Sales;Support;Engineering;HR;Finance;Marketing;Operations",
    "DEPT_SYNONYMS": "sls=Sales,tech support=Support,eng=Engineering,dev=Engineering,acct=Finance,acctg=Finance,mktg=Marketing,ops=Operations"
  },

  "hooks": {
    "on_job_start":  [{ "script": "hooks/on_job_start.py" }],
    "after_mapping": [{ "script": "hooks/after_mapping.py" }],
    "before_save":   [{ "script": "hooks/before_save.py" }],
    "on_job_end":    [{ "script": "hooks/on_job_end.py" }]
  },

  "columns": {
    "order": ["member_id","first_name","last_name","email","department","join_date","amount"],
    "meta": {
      "member_id": {
        "label": "Member ID", "required": true, "script": "column_detectors/member_id.py",
        "synonyms": ["member id","member#","id (member)","customer id","client id"],
        "type_hint": "string", "pattern": "^[A-Z0-9]{6,12}$"
      },
      "first_name": {
        "label": "First Name", "required": true, "script": "column_detectors/first_name.py",
        "synonyms": ["first name","given name","fname"], "type_hint": "string"
      },
      "last_name": {
        "label": "Last Name", "required": true, "script": "column_detectors/last_name.py",
        "synonyms": ["last name","surname","family name","lname"], "type_hint": "string"
      },
      "email": {
        "label": "Email", "required": true, "script": "column_detectors/email.py",
        "synonyms": ["email","e-mail","email address"], "type_hint": "string",
        "pattern": "^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$"
      },
      "department": {
        "label": "Department", "required": false, "script": "column_detectors/department.py",
        "synonyms": ["dept","division","team","org"], "type_hint": "string",
        "allowed": ["Sales","Support","Engineering","HR","Finance","Marketing","Operations"]
      },
      "join_date": {
        "label": "Join Date", "required": false, "script": "column_detectors/join_date.py",
        "synonyms": ["join date","start date","hire date","onboarded"], "type_hint": "date"
      },
      "amount": {
        "label": "Amount", "required": false, "script": "column_detectors/amount.py",
        "synonyms": ["amount","total","payment","fee","charge"], "type_hint": "number"
      }
    }
  }
}
```

---

## src/ade_config/config.env (optional)

<a id="configenv-optional"></a> [↑ back to tree](#top)

```dotenv
# Loaded before detectors/hooks import. Read via the `env` kwarg.

LOCALE=en-CA
DATE_FMT=%Y-%m-%d
AMOUNT_DECIMALS=2
FUTURE_DATE_GRACE_DAYS=7

# Canonical department labels + synonyms tuned by non-devs in the UI
DEPT_CANONICAL=Sales;Support;Engineering;HR;Finance;Marketing;Operations
DEPT_SYNONYMS=sls=Sales,tech support=Support,eng=Engineering,dev=Engineering,acct=Finance,acctg=Finance,mktg=Marketing,ops=Operations
```

---

## src/ade_config/_shared.py

<a id="sharedpy"></a> [↑ back to tree](#top)

```python
"""
_shared.py — small, dependency-free helpers used across detectors/transforms.

Design goals:
- Keep detectors tiny by centralizing common parsing/casing logic.
- Be explicit and deterministic (no locale-specific behavior).
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# ---------- Utility: safe ratio ---------------------------------------------

def ratio(numer: int, denom: int) -> float:
    return (numer / denom) if denom else 0.0

# ---------- Names -----------------------------------------------------------

def title_name(value: str | None) -> str | None:
    """
    Title-case names while preserving O'/Mc and separators.
    Examples: " mckay "→"McKay", "o'neil"→"O'Neil", "mary-jane"→"Mary-Jane"
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    base = s.lower()
    parts = re.split(r"([ -])", base)  # keep separators

    def fix(tok: str) -> str:
        t = tok.capitalize()
        if t.startswith("O'") and len(t) > 2:
            t = "O'" + t[2:].capitalize()
        if t.startswith("Mc") and len(t) > 2:
            t = "Mc" + t[2:].capitalize()
        return t

    return "".join(fix(p) if p not in {" ", "-"} else p for p in parts)

# ---------- Dates -----------------------------------------------------------

EXCEL_EPOCH = datetime(1899, 12, 30)  # Excel 1900 system
DATE_FORMATS = ["%Y-%m-%d","%m/%d/%Y","%d/%m/%Y","%b %d, %Y","%d %b %Y","%B %d, %Y","%Y%m%d"]

def is_date_like(v) -> bool:
    if v in (None, ""):
        return False
    if isinstance(v, (int, float)):
        return True  # Excel serials
    s = str(v).strip()
    return bool(s) and any(ch in s for ch in "-/ ,") and any(ch.isdigit() for ch in s)

def parse_date_to_iso(value, hint: str | None = None) -> str | None:
    """Return YYYY-MM-DD or None. Try env hint first, then a small format library, then serials."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return (EXCEL_EPOCH + timedelta(days=float(value))).strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(value).strip()
    if hint:
        try:
            return datetime.strptime(s, hint).strftime("%Y-%m-%d")
        except Exception:
            pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None

# ---------- Numbers ---------------------------------------------------------

CURRENCY_SYMBOLS = {"$", "£", "€", "¥", "₹"}

def to_decimal(raw) -> Decimal | None:
    """Parse currency-like strings. Handles commas and (accounting) negatives: "(123.45)"→-123.45."""
    if raw in (None, ""):
        return None
    s = str(raw).strip()
    for sym in CURRENCY_SYMBOLS:
        s = s.replace(sym, "")
    s = s.replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

def quantize_decimal(value: Decimal, decimals: int) -> Decimal:
    """ROUND_HALF_UP to requested precision."""
    q = Decimal(10) ** -decimals
    return value.quantize(q, rounding=ROUND_HALF_UP)
```

---

## Return‑shape quick reference

* **Detectors (row or column)** → `{"scores": { "<label or field_name>": float }}`
* **Transform** → `{"values": list, "warnings": list[str]}`
* **Validate** → `{"issues": [{"row_index": int, "code": str, "severity": "error"|"warning"|"info", "message": str}]}`

Keep detector deltas roughly **[-1.0, +1.0]** and preserve list lengths in transforms.

---

## src/ade_config/column_detectors/

<a id="column_detectors"></a> [↑ back to tree](#top)

### member_id.py

<a id="member_idpy"></a> [↑ back to tree](#top)

```python
"""
member_id.py — Stable IDs

What this teaches:
- Mapping = header synonyms + value regex shape + uniqueness hint.
- Transform = clean to uppercase alphanumerics.
- Validate = required, pattern, and duplicate values.

Examples
- header: "Member #"
- values: [" ab-123 ", None, "AB123", "ab—123"]  → transform → ["AB123", None, "AB123", "AB123"]
- issues: duplicates flagged if repeated after normalization.
"""

from __future__ import annotations
import re
from collections import Counter
from ade_config._shared import ratio

ID_RE = re.compile(r"^[A-Za-z0-9]{6,12}$")

def _clean_id(raw) -> str | None:
    if raw in (None, ""):
        return None
    return "".join(ch for ch in str(raw) if ch.isalnum()).upper() or None

# ---- mapping detectors ------------------------------------------------------

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(bool(ID_RE.match((_clean_id(v) or ""))) for v in values_sample)
    return {"scores": {field_name: round(ratio(hits, len(values_sample)), 2)}}

def detect_uniqueness_hint(*, values_sample: list, field_name: str, **_) -> dict:
    cleaned = [(_clean_id(v)) for v in values_sample if v not in (None, "")]
    uniq_ratio = ratio(len(set(cleaned)), len(cleaned))
    return {"scores": {field_name: 0.2 if uniq_ratio >= 0.9 else 0.0}}

# ---- transform --------------------------------------------------------------

def transform(*, values: list, field_name: str, **_) -> dict:
    normalized = [_clean_id(v) for v in values]
    blanks = sum(v is None for v in normalized)
    return {"values": normalized, "warnings": ([f"{field_name}: {blanks} blank → None"] if blanks else [])}

# ---- validate ---------------------------------------------------------------

def validate(*, values: list, field_name: str, field_meta: dict, **_) -> dict:
    issues = []
    if field_meta.get("required", False):
        for i, v in enumerate(values, start=1):
            if v in (None, ""):
                issues.append({"row_index": i, "code": "required_missing", "severity": "error",
                               "message": f"{field_name} is required."})
    for i, v in enumerate(values, start=1):
        if v not in (None, "") and not ID_RE.match(str(v)):
            issues.append({"row_index": i, "code": "invalid_format", "severity": "error",
                           "message": f"{field_name} must match {ID_RE.pattern}"})
    counts = Counter([v for v in values if v not in (None, "")])
    dupes = {val for val, c in counts.items() if c > 1}
    for i, v in enumerate(values, start=1):
        if v in dupes:
            issues.append({"row_index": i, "code": "duplicate_value", "severity": "error",
                           "message": f"{field_name} duplicate: {v}"})
    return {"issues": issues}
```

---

### first_name.py

<a id="first_namepy"></a> [↑ back to tree](#top)

```python
"""
first_name.py — Reader-friendly first names

What this teaches:
- Mapping = header synonyms + value-shape.
- Transform = careful title-casing (O'Neil, McKay, hyphens).
"""

from __future__ import annotations
import re
from ade_config._shared import title_name, ratio

NAMEISH = re.compile(r"^[A-Za-z][A-Za-z' -]{0,49}$")

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(1 for v in values_sample if v not in (None, "") and NAMEISH.match(str(v).strip()))
    return {"scores": {field_name: round(0.8 * ratio(hits, len(values_sample)), 2)}}

def transform(*, values: list, field_name: str, **_) -> dict:
    return {"values": [title_name(v) for v in values], "warnings": []}

def validate(*, values: list, field_name: str, field_meta: dict, **_) -> dict:
    issues = []
    if field_meta.get("required", False):
        for i, v in enumerate(values, start=1):
            if v in (None, ""):
                issues.append({"row_index": i, "code": "required_missing", "severity": "error",
                               "message": f"{field_name} is required."})
    return {"issues": issues}
```

---

### last_name.py

<a id="last_namepy"></a> [↑ back to tree](#top)

```python
"""
last_name.py — Mirror of first name logic with a slightly looser length bound.
"""

from __future__ import annotations
import re
from ade_config._shared import title_name, ratio

NAMEISH = re.compile(r"^[A-Za-z][A-Za-z' -]{0,64}$")

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(1 for v in values_sample if v not in (None, "") and NAMEISH.match(str(v).strip()))
    return {"scores": {field_name: round(0.8 * ratio(hits, len(values_sample)), 2)}}

def transform(*, values: list, field_name: str, **_) -> dict:
    return {"values": [title_name(v) for v in values], "warnings": []}

def validate(*, values: list, field_name: str, field_meta: dict, **_) -> dict:
    issues = []
    if field_meta.get("required", False):
        for i, v in enumerate(values, start=1):
            if v in (None, ""):
                issues.append({"row_index": i, "code": "required_missing", "severity": "error",
                               "message": f"{field_name} is required."})
    return {"issues": issues}
```

---

### email.py

<a id="emailpy"></a> [↑ back to tree](#top)

```python
"""
email.py — Emails with gentle repairs

What this teaches:
- Mapping = header synonyms + value pattern.
- Transform = lowercase + fix common domain typos.
- Validate = pattern + duplicate detection.

Edge cases handled:
" JACK@ACME.IO " → "jack@acme.io"
"ann@gmial.com"  → "ann@gmail.com"
"""

from __future__ import annotations
import re
from collections import Counter
from ade_config._shared import ratio

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
FIX_DOMAINS = {
    "gmial.com":"gmail.com", "gamil.com":"gmail.com",
    "hotnail.com":"hotmail.com", "outlok.com":"outlook.com", "yaho.com":"yahoo.com"
}

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(bool(EMAIL_RE.match(str(v).strip())) for v in values_sample if v not in (None, ""))
    return {"scores": {field_name: round(ratio(hits, len(values_sample)), 2)}}

def transform(*, values: list, field_name: str, **_) -> dict:
    out = []
    for v in values:
        if v in (None, ""):
            out.append(None); continue
        s = str(v).strip().lower()
        if "@" in s:
            local, _, domain = s.partition("@")
            s = f"{local}@{FIX_DOMAINS.get(domain, domain)}"
        out.append(s)
    return {"values": out, "warnings": []}

def validate(*, values: list, field_name: str, field_meta: dict, **_) -> dict:
    issues = []
    if field_meta.get("required", False):
        for i, v in enumerate(values, start=1):
            if v in (None, ""):
                issues.append({"row_index": i, "code": "required_missing", "severity": "error",
                               "message": f"{field_name} is required."})
    for i, v in enumerate(values, start=1):
        if v not in (None, "") and not EMAIL_RE.match(str(v)):
            issues.append({"row_index": i, "code": "invalid_format", "severity": "error",
                           "message": f"{field_name} must look like user@domain.tld"})
    counts = Counter([v for v in values if v not in (None, "")])
    dupes = {val for val, c in counts.items() if c > 1}
    for i, v in enumerate(values, start=1):
        if v in dupes:
            issues.append({"row_index": i, "code": "duplicate_value", "severity": "error",
                           "message": f"{field_name} duplicate: {v}"})
    return {"issues": issues}
```

---

### department.py

<a id="departmentpy"></a> [↑ back to tree](#top)

```python
"""
department.py — Canonical labels via env-driven synonyms

What this teaches:
- Transform maps synonyms to canonical, leaves unknowns unchanged.
- Validate warns (not errors) for values outside the canonical set.

Example env:
  DEPT_CANONICAL="Sales;Support;Engineering"
  DEPT_SYNONYMS="sls=Sales,tech support=Support,dev=Engineering"
values: ["sls","support","eng","finance"] → ["Sales","Support","eng","finance"]   (warn on 'eng'/'finance')
"""

from __future__ import annotations

def _parse_kv(spec: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not spec:
        return result
    for item in spec.split(","):
        k, sep, v = item.partition("=")
        if sep and k.strip() and v.strip():
            result[k.strip().lower()] = v.strip()
    return result

def _parse_list(spec: str | None) -> list[str]:
    return [s.strip() for s in (spec or "").split(";") if s.strip()]

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    textish = sum(isinstance(v, str) and v.strip() for v in values_sample)
    return {"scores": {field_name: round(0.4 * (textish / max(1, len(values_sample))), 2)}}

def transform(*, values: list, field_name: str, field_meta: dict, env: dict | None = None, **_) -> dict:
    env = env or {}
    canonical = set(_parse_list(env.get("DEPT_CANONICAL")) or field_meta.get("allowed", []))
    synonyms = _parse_kv(env.get("DEPT_SYNONYMS"))
    out: list[str | None] = []
    for raw in values:
        if raw in (None, ""):
            out.append(None); continue
        s = str(raw).strip()
        out.append(s if s in canonical else synonyms.get(s.lower(), s))
    return {"values": out, "warnings": []}

def validate(*, values: list, field_name: str, field_meta: dict, env: dict | None = None, **_) -> dict:
    env = env or {}
    allowed = set(_parse_list(env.get("DEPT_CANONICAL")) or field_meta.get("allowed", []))
    issues = []
    if allowed:
        for i, v in enumerate(values, start=1):
            if v not in (None, "") and v not in allowed:
                issues.append({"row_index": i, "code": "out_of_set", "severity": "warning",
                               "message": f"{field_name} '{v}' not in allowed set"})
    return {"issues": issues}
```

---

### join_date.py

<a id="join_datepy"></a> [↑ back to tree](#top)

```python
"""
join_date.py — From varied inputs to ISO YYYY-MM-DD

What this teaches:
- Mapping by “date-likeness”.
- Transform via env hint then known formats, plus Excel serials.
- Validate warns for future dates beyond a small grace window.

Example:
  DATE_FMT=%Y-%m-%d
  values: [45163, "09/15/2024", "15/09/2024", "Sep 15, 2024", ""]
  → ["2023-09-15","2024-09-15","2024-09-15","2024-09-15", None]
"""

from __future__ import annotations
from datetime import datetime, timedelta
from ade_config._shared import is_date_like, parse_date_to_iso

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    r = sum(is_date_like(v) for v in values_sample) / max(1, len(values_sample))
    return {"scores": {field_name: round(0.7 * r, 2)}}

def transform(*, values: list, field_name: str, env: dict | None = None, **_) -> dict:
    env = env or {}
    hint = env.get("DATE_FMT")
    return {"values": [parse_date_to_iso(v, hint) for v in values], "warnings": []}

def validate(*, values: list, field_name: str, env: dict | None = None, **_) -> dict:
    env = env or {}
    issues = []
    grace = int(env.get("FUTURE_DATE_GRACE_DAYS", "0"))
    future_cutoff = datetime.utcnow() + timedelta(days=grace)
    for i, v in enumerate(values, start=1):
        if v in (None, ""):
            continue
        try:
            dt = datetime.strptime(v, "%Y-%m-%d")
        except Exception:
            issues.append({"row_index": i, "code": "invalid_format", "severity": "error",
                           "message": f"{field_name} must be YYYY-MM-DD"})
            continue
        if dt > future_cutoff:
            issues.append({"row_index": i, "code": "out_of_range", "severity": "warning",
                           "message": f"{field_name} '{v}' is in the future"})
    return {"issues": issues}
```

---

### amount.py

<a id="amountpy"></a> [↑ back to tree](#top)

```python
"""
amount.py — Currency-lite parsing that’s deterministic

What this teaches:
- Mapping by “can parse as Decimal” ratio.
- Transform with ROUND_HALF_UP to env precision; cast to float for Excel writer.
- Validate with a simple non-negative check (customize as needed).

Example (AMOUNT_DECIMALS=2):
  values: ["$1,234.5", "(22.75)", "", 123] → [1234.50, -22.75, None, 123.00]
"""

from __future__ import annotations
from ade_config._shared import to_decimal, quantize_decimal, ratio

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.5 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h), 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    nums = sum(to_decimal(v) is not None for v in values_sample)
    return {"scores": {field_name: round(ratio(nums, len(values_sample)), 2)}}

def transform(*, values: list, field_name: str, env: dict | None = None, **_) -> dict:
    env = env or {}
    decimals = int(env.get("AMOUNT_DECIMALS", "2"))
    out: list[float | None] = []
    for v in values:
        d = to_decimal(v)
        out.append(None if d is None else float(quantize_decimal(d, decimals)))
    return {"values": out, "warnings": [f"{field_name}: rounded to {decimals} dp (ROUND_HALF_UP)"]}

def validate(*, values: list, field_name: str, **_) -> dict:
    issues = []
    for i, v in enumerate(values, start=1):
        if v is not None and v < 0:
            issues.append({"row_index": i, "code": "out_of_range", "severity": "warning",
                           "message": f"{field_name} is negative ({v})"})
    return {"issues": issues}
```

---

## src/ade_config/row_detectors/

<a id="row_detectors"></a> [↑ back to tree](#top)

### header.py

<a id="headerpy"></a> [↑ back to tree](#top)

```python
"""
header.py — Recognize headers with simple, explainable signals.

Signals:
- Text density: headers tend to be string-rich.
- Position bias: early rows are more likely headers.
- Numeric penalty: number-heavy rows look like data.
"""

from __future__ import annotations

def detect_text_density(*, row_values_sample: list, **_) -> dict:
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    if not non_blank:
        return {"scores": {"header": 0.0}}
    strings = sum(isinstance(c, str) for c in non_blank)
    ratio = strings / len(non_blank)
    bump = 0.7 if ratio >= 0.7 else (0.3 if ratio >= 0.5 else 0.0)
    return {"scores": {"header": bump}}

def detect_position_bias(*, row_index: int, **_) -> dict:
    boost = 0.4 if row_index <= 3 else (0.2 if row_index <= 6 else (0.1 if row_index <= 10 else 0.0))
    return {"scores": {"header": boost}}

def detect_numeric_penalty(*, row_values_sample: list, **_) -> dict:
    nums = sum(str(v).replace(".", "", 1).isdigit() for v in row_values_sample if v not in (None, ""))
    penalty = -0.3 if nums >= max(2, len(row_values_sample) // 2) else 0.0
    return {"scores": {"header": penalty}}
```

### data.py

<a id="datapy"></a> [↑ back to tree](#top)

```python
"""
data.py — Recognize data rows with complementary signals.

Signals:
- Numeric presence: at least one number.
- Reasonable blanks: some blanks are normal (not too many).
- Not header-like: very text-heavy rows get a small penalty.
"""

from __future__ import annotations

def detect_numeric_presence(*, row_values_sample: list, **_) -> dict:
    nums = sum(str(v).replace(".", "", 1).isdigit() for v in row_values_sample if v not in (None, ""))
    return {"scores": {"data": +0.4 if nums >= 1 else 0.0}}

def detect_blank_ratio(*, row_values_sample: list, **_) -> dict:
    total = len(row_values_sample) or 1
    blanks = sum(v in (None, "") for v in row_values_sample)
    r = blanks / total
    score = +0.2 if 0.0 < r <= 0.4 else (-0.2 if r >= 0.8 else 0.0)
    return {"scores": {"data": score}}

def detect_not_header_like(*, row_values_sample: list, **_) -> dict:
    non_blank = [v for v in row_values_sample if v not in (None, "")]
    if not non_blank:
        return {"scores": {"data": 0.0}}
    strings = sum(isinstance(v, str) for v in non_blank)
    ratio = strings / len(non_blank)
    return {"scores": {"data": -0.2 if ratio >= 0.8 else 0.0}}
```

---

## src/ade_config/hooks/

<a id="hooks"></a> [↑ back to tree](#top)

### on_job_start.py

<a id="on_job_startpy"></a> [↑ back to tree](#top)

```python
"""
on_job_start.py — Record provenance + quick env sanity.
"""

from __future__ import annotations

def run(*, job_id: str, manifest: dict, env: dict | None = None, **_):
    env = env or {}
    missing = [k for k in ("LOCALE", "DATE_FMT") if not env.get(k)]
    status = "OK" if not missing else f"Missing {', '.join(missing)}"
    return {"notes": f"Job {job_id} start | Locale={env.get('LOCALE','n/a')} | DateFmt={env.get('DATE_FMT','n/a')} | {status}"}
```

### after_mapping.py

<a id="after_mappingpy"></a> [↑ back to tree](#top)

```python
"""
after_mapping.py — Gentle guidance after mapping; avoid force-mapping.
"""

from __future__ import annotations

def run(*, table: dict | None = None, **_):
    if not table:
        return None
    unmapped_headers = {str(c.get("header","")).strip().lower() for c in table.get("unmapped", [])}
    mapped_fields = set((table.get("mapped") or {}).keys())
    if "work email" in unmapped_headers and "email" not in mapped_fields:
        return {"notes": "Hint: add 'Work Email' to email synonyms in manifest.json"}
    return None
```

### before_save.py

<a id="before_savepy"></a> [↑ back to tree](#top)

```python
"""
before_save.py — Add 'Summary', standardize, and (if supported) freeze/autosize.
"""

from __future__ import annotations

def run(*, book: object | None = None, artifact: dict | None = None, **_):
    if not (book and artifact):
        return None

    # 1) Summary: minimal, readable metrics
    try:
        total_rows = sum(len(t.get("rows", [])) for s in artifact.get("sheets", []) for t in s.get("tables", []))
        total_issues = sum(len(t.get("validation", {}).get("issues", []))
                           for s in artifact.get("sheets", []) for t in s.get("tables", []))
        if hasattr(book, "create_sheet"):
            book.create_sheet(name="Summary", rows=[["Metric","Value"],["Total rows", total_rows],["Total issues", total_issues]])
    except Exception:
        pass

    # 2) Standardize first sheet name
    if hasattr(book, "rename_sheet"):
        try:
            book.rename_sheet(old_name="Sheet1", new_name="Normalized")
        except Exception:
            pass

    # 3) Optional niceties
    if hasattr(book, "freeze_panes"):
        try:
            book.freeze_panes(sheet="Normalized", cell="A2")
        except Exception:
            pass
    if hasattr(book, "autosize_columns"):
        try:
            book.autosize_columns(sheet="Normalized")
        except Exception:
            pass

    return {"notes": "Added Summary; standardized sheet; optional header freeze/autosize if supported."}
```

### on_job_end.py

<a id="on_job_endpy"></a> [↑ back to tree](#top)

```python
"""
on_job_end.py — Compact issue breakdown for quick triage (code=count).
"""

from __future__ import annotations
from collections import Counter

def run(*, artifact: dict | None = None, **_):
    if not artifact:
        return None
    counts = Counter()
    for s in artifact.get("sheets", []):
        for t in s.get("tables", []):
            for issue in t.get("validation", {}).get("issues", []):
                counts[issue.get("code","other")] += 1
    total = sum(counts.values())
    breakdown = ", ".join(f"{code}={n}" for code, n in sorted(counts.items())) or "none"
    return {"notes": f"Issues: total={total}; {breakdown}"}
```

---

## src/ade_config/**init**.py

<a id="initpy"></a> [↑ back to tree](#top)

```python
# Empty is fine; marks src/ade_config/ as a Python package.
# Optional later: re-export helpers for convenience, e.g.:
#   from ._shared import title_name, parse_date_to_iso
```

---

### Final notes

* The **clickable tree** is now lean and professional (no legend), but each entry still explains *why it exists*.
* Every script favors **intuitive names**, small functions, and **inline examples** so authors can copy the pattern safely.
* The **contracts** (detector → transform → validate) are consistent, with return shapes repeated where they matter.

If you want, I can tailor the **synonyms**, **patterns**, and **examples** to your domain (e.g., invoices, enrollments, claims) so this becomes copy‑paste‑ready for your first production config.

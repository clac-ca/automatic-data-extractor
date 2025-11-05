# Config Packages — Click‑Through Reference (Masterclass Edition, Tree‑First)

<a id="top"></a>

**What is a config package?**
An ADE **config package** is an installable Python distribution that bundles your spreadsheet rules inside **`ade_config`**. ADE builds a dedicated virtual environment per configuration and reuses it for every run (**build once, run many**).

**Where does it live?**
Authored sources → `${ADE_DATA_DIR}/workspaces/<workspace_id>/config_packages/<config_id>/`
Built runtime → `${ADE_DATA_DIR}/workspaces/<workspace_id>/venvs/<config_id>/`

> **Runtime note:** Workers run in regular Python virtual environments. We **don’t hard‑block outbound network traffic**; keep rules pure, deterministic, and minimal. Only call the network if your use case *truly* requires it.

---

## Clickable Folder Tree (with inline comments)

> Click any item to jump to its section. This is the canonical mental model of a config.

* **my-config/**

  * **[pyproject.toml](#pyproject-toml)** — *Packaging metadata.* Declares an installable project so ADE can `pip install` your config into the per‑config venv.
  * **src/** — *Code lives under `src/` (src‑layout keeps packaging clean).*

    * **ade_config/** — *Your runtime package imported by the engine worker.*

      * **[manifest.json](#manifestjson)** — *Contract + behavior.* Engine defaults, column model, hooks.
      * **[config.env](#configenv-optional)** *(optional)* — *Feature flags & knobs* (e.g., `DATE_FMT`, canonical sets).
      * **[ _shared.py ](#sharedpy)** — *Tiny standard library.* Shared helpers used by detectors/transforms.
      * **[column_detectors/](#column_detectors)** — *Teach a field end‑to‑end (map → transform → validate).*

        * **[member_id.py](#member_idpy)** — *Stable IDs.* Synonyms, regex shape, uniqueness, duplicate checks.
        * **[first_name.py](#first_namepy)** — *Human names.* Title‑case (O’Neil, McKay, hyphens).
        * **[last_name.py](#last_namepy)** — *Same patterns as first name* for consistency.
        * **[email.py](#emailpy)** — *Emails.* Lowercasing, typo domain fixes, duplicates.
        * **[department.py](#departmentpy)** — *Controlled vocab.* Env‑driven synonyms → canonical set.
        * **[join_date.py](#join_datepy)** — *Dates.* Excel serials + flexible parsing → ISO `YYYY‑MM‑DD`.
        * **[amount.py](#amountpy)** — *Currency.* Strip symbols, quantize, non‑negative warning.
      * **[row_detectors/](#row_detectors)** — *Find tables & header rows by voting per row.*

        * **[header.py](#headerpy)** — *Looks like a header?* Text density, early‑row bias, numeric penalty.
        * **[data.py](#datapy)** — *Looks like data?* Numbers present, reasonable blanks, not header‑like.
      * **[hooks/](#hooks)** — *Small, safe pipeline extensions with structured context.*

        * **[on_job_start.py](#on_job_startpy)** — *Provenance & sanity checks* at job start.
        * **[after_mapping.py](#after_mappingpy)** — *Review/guide* after Pass 2 mapping (gentle suggestions).
        * **[before_save.py](#before_savepy)** — *Polish output* (summary tab, sheet rename, freeze panes).
        * **[on_job_end.py](#on_job_endpy)** — *Concise issue breakdown* for triage.
      * **[**init**.py](#initpy)** — *Empty is fine; marks `ade_config/` as a Python package.*

---

### (Optional) Copy‑paste ASCII tree (with comments)

```text
my-config/                             # ← Config project root (installable)
├─ pyproject.toml                      # ← Packaging metadata for ade_config
└─ src/
   └─ ade_config/                      # ← Runtime package imported by the worker
      ├─ manifest.json                 # ← Engine defaults, column model, hooks wiring
      ├─ config.env                    # ← OPTIONAL: env vars (e.g., DATE_FMT, canonical sets)
      ├─ _shared.py                    # ← Reusable helpers (name casing, date/number parsers)
      ├─ column_detectors/             # ← Field-by-field scripts: map → transform → validate
      │  ├─ member_id.py               #    Stable IDs (synonyms, regex shape, uniqueness, dups)
      │  ├─ first_name.py              #    Human names (smart title case: O'Neil, McKay)
      │  ├─ last_name.py               #    Mirror first_name patterns for consistency
      │  ├─ email.py                   #    Emails (lowercase, domain typo fixes, duplicates)
      │  ├─ department.py              #    Env-driven synonyms → canonical labels
      │  ├─ join_date.py               #    Excel serials + formats → YYYY-MM-DD
      │  └─ amount.py                  #    Currency parsing + precise quantize → float for writer
      ├─ row_detectors/                # ← Row-type voters: find headers & data regions
      │  ├─ header.py                  #    Text density, early-position bias, numeric penalty
      │  └─ data.py                    #    Numeric presence, reasonable blanks, not header-like
      ├─ hooks/                        # ← Small lifecycle extensions with safe context
      │  ├─ on_job_start.py            #    Provenance + sanity notes
      │  ├─ after_mapping.py           #    Gentle mapping hints (no force-mapping)
      │  ├─ before_save.py             #    Summary tab, sheet rename, optional freeze/autosize
      │  └─ on_job_end.py              #    Concise issue breakdown for triage
      └─ __init__.py                   # ← Empty OK; marks ade_config as a package
```

---

## pyproject.toml

<a id="pyproject-toml"></a> [↑ back to top](#top)

```toml
# pyproject.toml — defines the installable ADE config distribution.

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ade-config-membership"             # Unique per config across your workspace
version = "1.2.0"                           # Bump on publish
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

<a id="manifestjson"></a> [↑ back to top](#top)

> Shown in **JSONC** (JSON with comments). Remove comments in your real file.

```jsonc
{
  "config_script_api_version": "1",

  "info": {
    "schema": "ade.config-manifest/v1",
    "title": "Membership Rules",
    "version": "1.2.0"
  },

  "engine": {
    "defaults": {
      "timeout_ms": 180000,
      "memory_mb": 384,
      "mapping_score_threshold": 0.35  // If best score < 0.35, leave unmapped (safer)
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
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
        "label": "Member ID",
        "required": true,
        "script": "column_detectors/member_id.py",
        "synonyms": ["member id","member#","id (member)","customer id","client id"],
        "type_hint": "string",
        "pattern": "^[A-Z0-9]{6,12}$"
      },
      "first_name": {
        "label": "First Name",
        "required": true,
        "script": "column_detectors/first_name.py",
        "synonyms": ["first name","given name","fname"],
        "type_hint": "string"
      },
      "last_name": {
        "label": "Last Name",
        "required": true,
        "script": "column_detectors/last_name.py",
        "synonyms": ["last name","surname","family name","lname"],
        "type_hint": "string"
      },
      "email": {
        "label": "Email",
        "required": true,
        "script": "column_detectors/email.py",
        "synonyms": ["email","e-mail","email address"],
        "type_hint": "string",
        "pattern": "^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$"
      },
      "department": {
        "label": "Department",
        "required": false,
        "script": "column_detectors/department.py",
        "synonyms": ["dept","division","team","org"],
        "type_hint": "string",
        "allowed": ["Sales","Support","Engineering","HR","Finance","Marketing","Operations"]
      },
      "join_date": {
        "label": "Join Date",
        "required": false,
        "script": "column_detectors/join_date.py",
        "synonyms": ["join date","start date","hire date","onboarded"],
        "type_hint": "date"
      },
      "amount": {
        "label": "Amount",
        "required": false,
        "script": "column_detectors/amount.py",
        "synonyms": ["amount","total","payment","fee","charge"],
        "type_hint": "number"
      }
    }
  }
}
```

---

## src/ade_config/config.env (optional)

<a id="configenv-optional"></a> [↑ back to top](#top)

```dotenv
# Loaded before detectors/hooks import. Scripts read via the `env` kwarg.

LOCALE=en-CA
DATE_FMT=%Y-%m-%d
AMOUNT_DECIMALS=2
FUTURE_DATE_GRACE_DAYS=7

DEPT_CANONICAL=Sales;Support;Engineering;HR;Finance;Marketing;Operations
DEPT_SYNONYMS=sls=Sales,tech support=Support,eng=Engineering,dev=Engineering,acct=Finance,acctg=Finance,mktg=Marketing,ops=Operations
```

---

## src/ade_config/_shared.py

<a id="sharedpy"></a> [↑ back to top](#top)

```python
"""
_shared.py — reusable helpers (name casing, date/number parsers, tiny scorers).
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")

def normalize_header(s: str | None) -> str:
    if not s:
        return ""
    s = NON_ALNUM.sub(" ", str(s).lower()).strip()
    return re.sub(r"\s+", " ", s)

def name_title(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    base = s.lower()
    def fix(tok: str) -> str:
        t = tok.capitalize()
        if t.startswith("O'") and len(t) > 2:
            t = "O'" + t[2:].capitalize()
        if t.startswith("Mc") and len(t) > 2:
            t = "Mc" + t[2:].capitalize()
        return t
    parts = re.split(r"([ -])", base)
    return "".join(fix(p) if p not in {" ", "-"} else p for p in parts)

# Dates
EXCEL_EPOCH = datetime(1899, 12, 30)
DATE_FORMATS = ["%Y-%m-%d","%m/%d/%Y","%d/%m/%Y","%b %d, %Y","%d %b %Y","%B %d, %Y","%Y%m%d"]

def is_date_like(v) -> bool:
    if v in (None, ""):
        return False
    if isinstance(v, (int, float)):
        return True
    s = str(v).strip()
    return bool(s) and any(ch in s for ch in "-/ ,") and any(ch.isdigit() for ch in s)

def parse_date_to_iso(value, hint: str | None = None) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            dt = EXCEL_EPOCH + timedelta(days=float(value))
            return dt.strftime("%Y-%m-%d")
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

# Numbers
CURRENCY_SYMBOLS = {"$", "£", "€", "¥", "₹"}

def to_decimal(raw) -> Decimal | None:
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
    q = Decimal(10) ** -decimals
    return value.quantize(q, rounding=ROUND_HALF_UP)
```

---

## src/ade_config/column_detectors/

<a id="column_detectors"></a> [↑ back to top](#top)

**Scoring pattern:** Each `detect_*` returns `{"scores": {<field_name>: float}}` in **[-1.0, +1.0]**.
Prefer multiple tiny signals over one large function (clearer audit trail).

### member_id.py

<a id="member_idpy"></a>

```python
from __future__ import annotations
import re
from collections import Counter

ID_RE = re.compile(r"^[A-Za-z0-9]{6,12}$")

def _clean(raw) -> str | None:
    if raw in (None, ""):
        return None
    return "".join(ch for ch in str(raw) if ch.isalnum()).upper() or None

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score += 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
        score = min(score, 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(bool(ID_RE.match((_clean(v) or ""))) for v in values_sample)
    ratio = hits / max(1, len(values_sample))
    return {"scores": {field_name: round(ratio, 2)}}

def detect_uniqueness_hint(*, values_sample: list, field_name: str, **_) -> dict:
    cleaned = [(_clean(v)) for v in values_sample if v not in (None, "")]
    uniq_ratio = len(set(cleaned)) / max(1, len(cleaned))
    return {"scores": {field_name: 0.2 if uniq_ratio >= 0.9 else 0.0}}

def transform(*, values: list, field_name: str, **_) -> dict:
    normalized = [_clean(v) for v in values]
    blanks = sum(v is None for v in normalized)
    warnings = [f"{field_name}: {blanks} blank → None"] if blanks else []
    return {"values": normalized, "warnings": warnings}

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

<a id="first_namepy"></a>

```python
from __future__ import annotations
import re
from ade_config._shared import name_title

NAMEISH = re.compile(r"^[A-Za-z][A-Za-z' -]{0,49}$")

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score += 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
        score = min(score, 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(1 for v in values_sample if v not in (None, "") and NAMEISH.match(str(v).strip()))
    ratio = hits / max(1, len(values_sample))
    return {"scores": {field_name: round(0.8 * ratio, 2)}}

def transform(*, values: list, field_name: str, **_) -> dict:
    return {"values": [name_title(v) for v in values], "warnings": []}

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

<a id="last_namepy"></a>

```python
from __future__ import annotations
import re
from ade_config._shared import name_title

NAMEISH = re.compile(r"^[A-Za-z][A-Za-z' -]{0,64}$")

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score += 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
        score = min(score, 0.9)
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(1 for v in values_sample if v not in (None, "") and NAMEISH.match(str(v).strip()))
    ratio = hits / max(1, len(values_sample))
    return {"scores": {field_name: round(0.8 * ratio, 2)}}

def transform(*, values: list, field_name: str, **_) -> dict:
    return {"values": [name_title(v) for v in values], "warnings": []}

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

<a id="emailpy"></a>

```python
from __future__ import annotations
import re
from collections import Counter

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
FIX_DOMAINS = {"gmial.com":"gmail.com","gamil.com":"gmail.com","hotnail.com":"hotmail.com",
               "outlok.com":"outlook.com","yaho.com":"yahoo.com"}

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score += 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
    return {"scores": {field_name: min(score, 0.9)}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(bool(EMAIL_RE.match(str(v).strip())) for v in values_sample if v not in (None, ""))
    ratio = hits / max(1, len(values_sample))
    return {"scores": {field_name: round(ratio, 2)}}

def detect_at_symbol_ratio(*, values_sample: list, field_name: str, **_) -> dict:
    ats = sum("@" in str(v) for v in values_sample if v not in (None, ""))
    ratio = ats / max(1, len(values_sample))
    return {"scores": {field_name: round(0.3 * ratio, 2)}}

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

<a id="departmentpy"></a>

```python
from __future__ import annotations

def _parse_kv_pairs(spec: str | None) -> dict[str, str]:
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
        score += 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
    return {"scores": {field_name: min(score, 0.9)}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    textish = sum(isinstance(v, str) and v.strip() for v in values_sample)
    ratio = textish / max(1, len(values_sample))
    return {"scores": {field_name: round(0.4 * ratio, 2)}}

def transform(*, values: list, field_name: str, field_meta: dict, env: dict | None = None, **_) -> dict:
    env = env or {}
    canonical = set(_parse_list(env.get("DEPT_CANONICAL")) or field_meta.get("allowed", []))
    synonyms = _parse_kv_pairs(env.get("DEPT_SYNONYMS"))
    out: list[str | None] = []
    for raw in values:
        if raw in (None, ""):
            out.append(None); continue
        s = str(raw).strip()
        if s in canonical:
            out.append(s); continue
        out.append(synonyms.get(s.lower(), s))  # leave unknowns; validator will warn
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

<a id="join_datepy"></a>

```python
from __future__ import annotations
from datetime import datetime, timedelta
from ade_config._shared import is_date_like, parse_date_to_iso

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score += 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
    return {"scores": {field_name: min(score, 0.9)}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    ratio = sum(is_date_like(v) for v in values_sample) / max(1, len(values_sample))
    return {"scores": {field_name: round(0.7 * ratio, 2)}}

def transform(*, values: list, field_name: str, env: dict | None = None, **_) -> dict:
    env = env or {}
    hint = env.get("DATE_FMT")
    out = [parse_date_to_iso(v, hint) for v in values]
    return {"values": out, "warnings": []}

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

<a id="amountpy"></a>

```python
from __future__ import annotations
from ade_config._shared import to_decimal, quantize_decimal

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score += 0.5 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
    return {"scores": {field_name: min(score, 0.9)}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    nums = sum(to_decimal(v) is not None for v in values_sample)
    ratio = nums / max(1, len(values_sample))
    return {"scores": {field_name: round(ratio, 2)}}

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

<a id="row_detectors"></a> [↑ back to top](#top)

### header.py

<a id="headerpy"></a>

```python
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

<a id="datapy"></a>

```python
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

<a id="hooks"></a> [↑ back to top](#top)

### on_job_start.py

<a id="on_job_startpy"></a>

```python
from __future__ import annotations

def run(*, job_id: str, manifest: dict, env: dict | None = None, **_):
    env = env or {}
    missing = [k for k in ("LOCALE", "DATE_FMT") if not env.get(k)]
    status = "OK" if not missing else f"Missing {', '.join(missing)}"
    return {"notes": f"Job {job_id} start | Locale={env.get('LOCALE','n/a')} | DateFmt={env.get('DATE_FMT','n/a')} | {status}"}
```

### after_mapping.py

<a id="after_mappingpy"></a>

```python
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

<a id="before_savepy"></a>

```python
from __future__ import annotations

def run(*, book: object | None = None, artifact: dict | None = None, **_):
    if not (book and artifact):
        return None

    try:
        total_rows = sum(len(t.get("rows", [])) for s in artifact.get("sheets", []) for t in s.get("tables", []))
        total_issues = sum(len(t.get("validation", {}).get("issues", []))
                           for s in artifact.get("sheets", []) for t in s.get("tables", []))
        if hasattr(book, "create_sheet"):
            book.create_sheet(name="Summary", rows=[["Metric","Value"],["Total rows", total_rows],["Total issues", total_issues]])
    except Exception:
        pass

    if hasattr(book, "rename_sheet"):
        try:
            book.rename_sheet(old_name="Sheet1", new_name="Normalized")
        except Exception:
            pass

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

    return {"notes": "Added Summary; standardized sheet; applied optional header freeze/autosize if supported."}
```

### on_job_end.py

<a id="on_job_endpy"></a>

```python
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

<a id="initpy"></a> [↑ back to top](#top)

```python
# Empty is fine; marks src/ade_config/ as a Python package.
# Optionally re-export helpers later, e.g.:
#   from ._shared import name_title, parse_date_to_iso
```

---

## Quick Reference: Patterns & Anti‑Patterns

**Patterns that work well**

* Compose *several tiny detectors* (synonyms, value shape, simple heuristics).
* Keep detectors **pure** and **fast**; put heavier work in transforms/validators.
* Prefer env‑driven knobs (`DATE_FMT`, canonical lists) so non‑devs can adjust behavior safely.
* Return the exact small shapes (`{"scores":{}}`, `{"values":[], "warnings":[]}`, `{"issues":[]}`).

**Anti‑patterns to avoid**

* Doing file or network I/O inside detectors.
* Transform functions that change row order or column length.
* Validators that emit unstructured strings (use `{row_index, code, severity, message}`).
* One mega‑detector that tries to do everything (hurts explainability).

---

### Next steps

1. Publish this config as a **draft** in the UI.
2. Click **Build** to create the per‑config venv (engine + your config).
3. **Run** a sample file and open the job’s `artifact.json` to see detector scores, mappings, transforms, and issues step‑by‑step.

If you want, I can now tailor the **tree annotations** for your domain (e.g., healthcare claims, invoices, inventory) so the first‑time reader sees examples in their own language.
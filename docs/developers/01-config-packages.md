# Config Packages — quick tour & how it runs


An ADE **config package** is a small, installable Python project (**`ade_config`**) that teaches the engine how to read messy spreadsheets and write a clean workbook. You write simple Python functions; the engine streams files, calls your functions, and records every step in an **artifact** (audit trail).

---
<a id="top"></a>

## Clickable project explorer (start here)

* **my-config/**

  * **[pyproject.toml](#pyprojecttoml)** — packaging metadata (installable; `src/` layout)
  * **src/**

    * **ade_config/** — the runtime package the engine imports

      * **[manifest.json](#manifestjson)** — engine defaults, column model, hooks
      * **[config.env](#configenv)** *(optional)* — environment knobs (e.g., `DATE_FMT`)
      * **[_shared.py](#sharedpy)** — tiny helpers (names, dates, numbers)
      * **[column_detectors/](#columndetectors)** — one file per **canonical field**

        * **[member_id.py](#memberidpy)** — ID mapping → normalize → validate
        * **[full_name.py](#fullnamepy)** — multi‑field transform (`→ first_name`, `last_name`)
        * **[first_name.py](#firstnamepy)**, **[last_name.py](#lastnamepy)**
        * **[email.py](#emailpy)**, **[department.py](#departmentpy)**, **[join_date.py](#joindatepy)**, **[amount.py](#amountpy)**
      * **[row_detectors/](#rowdetectors)** — row‑by‑row “is this header/data?” voters

        * **[header.py](#headerpy)**, **[data.py](#datapy)**
      * **[hooks/](#hooks)** — life‑cycle touches

        * **[on_job_start.py](#onjobstartpy)**, **[after_mapping.py](#aftermappingpy)**, **[before_save.py](#beforesavepy)**, **[on_job_end.py](#onjobendpy)**
      * **[**init**.py](#initpy)** — marks the package

---

## The idea in plain English

The **engine** runs inside a **virtual environment** that contains the engine + your `ade_config`. It opens spreadsheets in **streaming** mode (memory‑light), and calls your functions at a few simple moments:

1. **Row streaming → find tables.**
   The engine goes **row by row** and calls every function named **`detect_*`** in `row_detectors/header.py` and `row_detectors/data.py`. Each function returns tiny **scores** like “this row looks like a **header**” or “this row looks like **data**.” From these labels the engine finds **table regions** (start/end + header row), and logs the details in the **artifact**.

2. **Per table → identify columns.**
   For each table region (one at a time), the engine builds a small in‑memory view and calls every **`detect_*`** in each field module under `column_detectors/`. Detectors return **scores** (“this column looks like `member_id`”). The engine picks a best match per column. If enabled in `manifest.json`, any **unmatched columns** are appended **on the far right** using a `raw_…` prefix.

3. **Row by row → transform & validate.**
   For each **row** in the table, the engine calls a **`transform()`** (if present) for each mapped field. A transform returns a small **delta dict** (it can fill **multiple fields** — e.g., `full_name` → `first_name` & `last_name`). Then a **`validate()`** (if present) returns any row‑level issues. Every decision is added to the **artifact**.

4. **Hooks → light polish.**

* `on_job_start(job)` → return **None** (log/setup).
* `after_mapping(worksheet, table)` → return the **same table** (you may edit header cells, etc.).
* `before_save(workbook)` → return the **workbook** (rename sheets, add “Summary,” freeze panes, optional Excel structured table).
* `on_job_end(artifact)` → return **None** (summaries/logs).

That’s it: **stream → find tables → map columns → transform/validate → write → polish → save**. The **artifact** keeps a precise, reproducible trail.
[Back to top](#top)

---

## What functions the engine looks for (simple rules)

* In **row detectors** (`row_detectors/*.py`), any top‑level function named **`detect_*`** will be called for each row and must return a small score dict. Define as many as you like; the engine **sums** their effects.
* In **column detectors** (`column_detectors/<field>.py`), any top‑level **`detect_*`** will be called on each raw column to score whether that column matches **that field**.
* In each **column** file, if you define **`transform()`** or **`validate()`**, the engine calls them **row‑by‑row** for mapped rows.
* In **hooks** (`hooks/*.py`), the engine calls these **exact names**:
  `on_job_start`, `after_mapping`, `before_save`, `on_job_end`.

All calls are **keyword‑only**. It’s safe to accept `**_` for future compatibility.
[Back to top](#top)

---

## Call & return (complete quick reference)

| Stage           | Where                         | Engine calls    | You get (kwargs)                                                                                                                                                                       | You return                                                                    |
| --------------- | ----------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Job start       | `hooks/on_job_start.py`       | `on_job_start`  | `job_id`, `manifest`, `env`, `artifact`, `logger`                                                                                                                                      | `None`                                                                        |
| Row detection   | `row_detectors/header.py`     | all `detect_*`  | `row_index`, `row_values_sample`, `sheet_name`, `manifest`, `env`, `artifact`, `logger`                                                                                                | `{"scores":{"header": float}}`                                                |
| Row detection   | `row_detectors/data.py`       | all `detect_*`  | same as above                                                                                                                                                                          | `{"scores":{"data": float}}`                                                  |
| Column mapping  | `column_detectors/<field>.py` | all `detect_*`  | `worksheet` (OpenPyXL), `table_ref` (A1 range), `column_index` (1‑based inside region), `header`, `values_sample`, `field_name`, `field_meta`, `manifest`, `env`, `artifact`, `logger` | `{"scores":{"<field_name>": float}}`                                          |
| After mapping   | `hooks/after_mapping.py`      | `after_mapping` | `worksheet` (OpenPyXL), `table` (OpenPyXL `Table`), `logger`                                                                                                                           | **the same `table`** (possibly mutated)                                       |
| Transform (row) | `column_detectors/<field>.py` | `transform`     | `row_index`, `field_name`, `value` (raw cell), `row` (dict of canonical fields), `manifest`, `env`, `artifact`, `logger`                                                               | **delta dict**, e.g. `{"first_name": "…", "last_name": "…"}` (or `{}`/`None`) |
| Validate (row)  | `column_detectors/<field>.py` | `validate`      | `row_index`, `field_name`, `value` (post‑transform), `row` (post‑merge), `manifest`, `env`, `artifact`, `logger`                                                                       | list of issues (or `[]`)                                                      |
| Before save     | `hooks/before_save.py`        | `before_save`   | `workbook` (OpenPyXL `Workbook`), `artifact`, `logger`                                                                                                                                 | **`workbook`** (same or replacement)                                          |
| Job end         | `hooks/on_job_end.py`         | `on_job_end`    | `artifact`, `logger`                                                                                                                                                                   | `None`                                                                        |

Tip: **Unmatched** columns go to the right **if** `manifest.engine.writer.append_unmapped_columns = true` (using `unmapped_prefix`).
[Back to top](#top)

---

## Minimal, copy‑ready examples

### Row detector — `row_detectors/header.py`

<a id="rowdetectors"></a><a id="headerpy"></a>

```python
# Called for every row; you can define many detect_* functions.
def detect_text_density(*, row_values_sample: list, **_) -> dict:
    non_blank = [c for c in row_values_sample if c not in (None, "")]
    if not non_blank:
        return {"scores": {"header": 0.0}}
    strings = sum(isinstance(c, str) for c in non_blank)
    ratio = strings / len(non_blank)
    return {"scores": {"header": 0.7 if ratio >= 0.7 else (0.3 if ratio >= 0.5 else 0.0)}}
```

[Back to top](#top)

### Row detector — `row_detectors/data.py`

<a id="datapy"></a>

```python
def detect_numeric_presence(*, row_values_sample: list, **_) -> dict:
    nums = sum(str(v).replace(".", "", 1).isdigit() for v in row_values_sample if v not in (None, ""))
    return {"scores": {"data": +0.4 if nums >= 1 else 0.0}}

def detect_not_header_like(*, row_values_sample: list, **_) -> dict:
    non_blank = [v for v in row_values_sample if v not in (None, "")]
    if not non_blank: return {"scores": {"data": 0.0}}
    strings = sum(isinstance(v, str) for v in non_blank)
    r = strings / len(non_blank)
    return {"scores": {"data": -0.2 if r >= 0.8 else 0.0}}
```

[Back to top](#top)

### Column detector — `column_detectors/member_id.py`

<a id="columndetectors"></a><a id="memberidpy"></a>

```python
import re
ID = re.compile(r"^[A-Za-z0-9]{6,12}$")

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    score = 0.0
    if header:
        h = header.lower()
        score = min(0.9, 0.6 * sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h))
    return {"scores": {field_name: score}}

def detect_value_shape(*, values_sample: list, field_name: str, **_) -> dict:
    hits = sum(1 for v in values_sample if v not in (None, "") and ID.match(str(v).strip()))
    return {"scores": {field_name: round(hits / max(1, len(values_sample)), 2)}}

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    """Normalize to uppercase alphanumerics."""
    if value in (None, ""): return None
    s = "".join(ch for ch in str(value) if ch.isalnum()).upper() or None
    return {"member_id": s} if s else None

def validate(*, row_index: int, field_name: str, value, row: dict, field_meta: dict, **_) -> list[dict]:
    issues = []
    if field_meta.get("required", False) and (value in (None, "")):
        issues.append({"row_index": row_index, "code": "required_missing", "severity": "error",
                       "message": f"{field_name} is required."})
    if value not in (None, "") and not ID.match(str(value)):
        issues.append({"row_index": row_index, "code": "invalid_format", "severity": "error",
                       "message": f"{field_name} must match {ID.pattern}"})
    return issues
```

[Back to top](#top)

### Transform that populates multiple fields — `column_detectors/full_name.py`

<a id="fullnamepy"></a>

```python
from ade_config._shared import title_name

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    """
    Accept the cell value for 'full_name' and return a small delta dict
    that can fill several fields in the current row.
    """
    if value in (None, ""):
        return None
    full = title_name(str(value))
    if not full:
        return None
    parts = [p for p in full.split(" ") if p]
    first = parts[0] if parts else None
    last  = parts[-1] if len(parts) > 1 else None
    return {"full_name": full, "first_name": first, "last_name": last}
```

[Back to top](#top)

### Email, Department, Dates, Amount — tiny patterns

<a id="emailpy"></a><a id="departmentpy"></a><a id="joindatepy"></a><a id="amountpy"></a>

```python
# email.py (transform) — lowercase + fix a few common domains; validate pattern
import re
DOMAINS = {"gmial.com":"gmail.com","gamil.com":"gmail.com","outlok.com":"outlook.com"}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    if value in (None, ""): return None
    s = str(value).strip().lower()
    if "@" in s:
        local, _, domain = s.partition("@")
        s = f"{local}@{DOMAINS.get(domain, domain)}"
    return {"email": s}

def validate(*, row_index: int, field_name: str, value, row: dict, field_meta: dict, **_) -> list[dict]:
    return [] if (value in (None, "") or EMAIL.match(str(value))) else [
        {"row_index": row_index, "code": "invalid_format", "severity": "error",
         "message": f"{field_name} must look like user@domain.tld"}]
```

```python
# department.py (transform) — map synonyms to canonical labels from env/manifest
def transform(*, row_index: int, field_name: str, value, row: dict, manifest: dict, env: dict | None = None, **_) -> dict | None:
    env = env or {}
    allowed = set((env.get("DEPT_CANONICAL") or "").split(";")) if env.get("DEPT_CANONICAL") else set(manifest["columns"]["meta"]["department"].get("allowed", []))
    synonyms = {}
    for kv in (env.get("DEPT_SYNONYMS") or "").split(","):
        k, _, v = kv.partition("=")
        if k.strip() and v.strip(): synonyms[k.strip().lower()] = v.strip()
    if value in (None, ""): return None
    s = str(value).strip()
    return {"department": s if s in allowed else synonyms.get(s.lower(), s)}
```

```python
# join_date.py (transform) — parse to ISO YYYY-MM-DD (Excel serials & common formats)
from datetime import datetime, timedelta
EXCEL_EPOCH = datetime(1899, 12, 30)
FORMATS = ["%Y-%m-%d","%m/%d/%Y","%d/%m/%Y","%b %d, %Y","%d %b %Y","%Y%m%d"]

def transform(*, row_index: int, field_name: str, value, row: dict, env: dict | None = None, **_) -> dict | None:
    if value in (None, ""): return None
    if isinstance(value, (int, float)):
        try: return {"join_date": (EXCEL_EPOCH + timedelta(days=float(value))).strftime("%Y-%m-%d")}
        except Exception: return None
    s = str(value).strip()
    fmt = (env or {}).get("DATE_FMT")
    try:
        if fmt: return {"join_date": datetime.strptime(s, fmt).strftime("%Y-%m-%d")}
    except Exception: pass
    for f in FORMATS:
        try: return {"join_date": datetime.strptime(s, f).strftime("%Y-%m-%d")}
        except Exception: continue
    return None
```

```python
# amount.py (transform) — parse currency-like strings and round to env precision
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
def _to_decimal(x):
    if x in (None, ""): return None
    s = str(x).strip().replace(",", "")
    for sym in "$£€¥₹": s = s.replace(sym, "")
    if s.startswith("(") and s.endswith(")"): s = "-" + s[1:-1]
    try: return Decimal(s)
    except InvalidOperation: return None

def transform(*, row_index: int, field_name: str, value, row: dict, env: dict | None = None, **_) -> dict | None:
    d = _to_decimal(value)
    if d is None: return None
    decimals = int((env or {}).get("AMOUNT_DECIMALS", "2"))
    q = Decimal(10) ** -decimals
    return {"amount": float(d.quantize(q, rounding=ROUND_HALF_UP))}
```

[Back to top](#top)

---

## Hooks — light, predictable, typed

<a id="hooks"></a>

**Objects you’ll see:**

* `worksheet` and `workbook` are real **OpenPyXL** objects.
* `table` is an **OpenPyXL `Table`** (useful for ref/style); mapping metadata lives in the artifact and engine context.
* Use the provided `logger` to write messages; `on_job_start` / `on_job_end` return **None**.

### `hooks/after_mapping.py` — mutate table headers; return the table

<a id="aftermappingpy"></a>

```python
from openpyxl.worksheet.worksheet import Worksheet  # type: ignore
from openpyxl.worksheet.table import Table as XLTable # type: ignore
from openpyxl.utils.cell import coordinate_from_string, column_index_from_string # type: ignore

def _header_row(ref: str) -> tuple[int, int, int]:
    min_a1, max_a1 = ref.split(":")
    (min_col_letters, min_row) = coordinate_from_string(min_a1)
    (max_col_letters, _)       = coordinate_from_string(max_a1)
    return (min_row, column_index_from_string(min_col_letters), column_index_from_string(max_col_letters))

def after_mapping(*, worksheet: Worksheet, table: XLTable, logger=None, **_) -> XLTable:
    """Normalize header labels (e.g., 'Work Email' → 'Email') and return the same table."""
    try:
        row, cmin, cmax = _header_row(table.ref)
        for col_idx in range(cmin, cmax + 1):
            cell = worksheet.cell(row=row, column=col_idx)
            if str(cell.value).strip().lower() == "work email":
                cell.value = "Email"
                if logger: logger.info("after_mapping: normalized header at %s", cell.coordinate)
    except Exception:
        if logger: logger.debug("after_mapping: header edit skipped", exc_info=False)
    return table
```

[Back to top](#top)

### `hooks/before_save.py` — polish workbook; return workbook

<a id="beforesavepy"></a>

```python
from openpyxl.workbook import Workbook          # type: ignore
from openpyxl.utils import get_column_letter    # type: ignore
from openpyxl.worksheet.table import Table, TableStyleInfo  # type: ignore

def before_save(*, workbook: Workbook, artifact: dict | None = None, logger=None, **_) -> Workbook:
    """Rename, freeze, add Summary, optional Excel 'structured table', autosize; then return workbook."""
    ws = workbook.active
    if ws.title != "Normalized":
        ws.title = "Normalized"
    ws.freeze_panes = "A2"

    total_rows = sum(len(t.get("rows", [])) for s in (artifact or {}).get("sheets", []) for t in s.get("tables", []))
    total_issues = sum(len(t.get("validation", {}).get("issues", [])) for s in (artifact or {}).get("sheets", []) for t in s.get("tables", []))
    summary = workbook.create_sheet("Summary")
    summary.append(["Metric", "Value"])
    summary.append(["Total rows", total_rows])
    summary.append(["Total issues", total_issues])

    if ws.max_row and ws.max_column:
        ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
        tbl = Table(displayName="NormalizedTable", ref=ref)
        tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
        ws.add_table(tbl)
        for c in range(1, ws.max_column + 1):
            letter, width = get_column_letter(c), 10
            try:
                width = max(width, max((len(str(cell.value)) for cell in ws[letter] if cell.value is not None), default=10) + 2)
            except Exception:
                pass
            ws.column_dimensions[letter].width = min(60, width)
    return workbook
```

[Back to top](#top)

### `hooks/on_job_start.py` & `hooks/on_job_end.py` — log; return None

<a id="onjobstartpy"></a><a id="onjobendpy"></a>

```python
# on_job_start.py
def on_job_start(*, job_id: str, manifest: dict, env: dict | None = None, artifact: dict | None = None, logger=None, **_) -> None:
    env = env or {}
    if logger:
        logger.info("job_start id=%s locale=%s date_fmt=%s",
                    job_id, env.get("LOCALE","n/a"), env.get("DATE_FMT","n/a"))
    return None
```

```python
# on_job_end.py
from collections import Counter
def on_job_end(*, artifact: dict | None = None, logger=None, **_) -> None:
    if not artifact:
        if logger: logger.warning("on_job_end: missing artifact")
        return None
    counts = Counter()
    for s in artifact.get("sheets", []):
        for t in s.get("tables", []):
            for issue in t.get("validation", {}).get("issues", []):
                counts[issue.get("code","other")] += 1
    total = sum(counts.values())
    if logger:
        breakdown = ", ".join(f"{code}={n}" for code, n in sorted(counts.items())) or "none"
        logger.info("on_job_end: issues_total=%s | %s", total, breakdown)
    return None
```

[Back to top](#top)

---

## Appendix: `pyproject.toml`, `manifest.json`, and small helpers

### `pyproject.toml`

<a id="pyprojecttoml"></a>

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ade-config-membership"
version = "1.8.0"
requires-python = ">=3.11"
description = "ADE configuration: streaming detectors, row-level transforms, validators, hooks"
readme = "README.md"

[tool.setuptools]
package-dir = {"" = "src"}
[tool.setuptools.packages.find]
where = ["src"]
include = ["ade_config*"]

[tool.ade]
display_name = "Membership Normalization"
min_engine = ">=0.4.0"
tags = ["membership","hr","finance"]
```

[Back to top](#top)

### `manifest.json`

<a id="manifestjson"></a>

```json
{
  "config_script_api_version": "1",
  "engine": {
    "defaults": {
      "timeout_ms": 180000,
      "memory_mb": 384,
      "mapping_score_threshold": 0.35
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
  },
  "columns": {
    "order": ["member_id","full_name","first_name","last_name","email","department","join_date","amount"],
    "meta": {
      "member_id":  { "label":"Member ID", "required":true,  "script":"column_detectors/member_id.py",
                      "synonyms": ["member id","member#","id (member)","customer id","client id"] },
      "full_name":  { "label":"Full Name", "script":"column_detectors/full_name.py",
                      "synonyms": ["full name","name","employee name"] },
      "first_name": { "label":"First Name", "required":true,  "script":"column_detectors/first_name.py",
                      "synonyms": ["first name","given name","fname"] },
      "last_name":  { "label":"Last Name", "required":true,  "script":"column_detectors/last_name.py",
                      "synonyms": ["last name","surname","family name","lname"] },
      "email":      { "label":"Email", "required":true,      "script":"column_detectors/email.py",
                      "synonyms": ["email","e-mail","email address"] },
      "department": { "label":"Department", "script":"column_detectors/department.py",
                      "synonyms": ["dept","division","team","org"] },
      "join_date":  { "label":"Join Date", "script":"column_detectors/join_date.py",
                      "synonyms": ["join date","start date","hire date","onboarded"] },
      "amount":     { "label":"Amount", "script":"column_detectors/amount.py",
                      "synonyms": ["amount","total","payment","fee","charge"] }
    }
  }
}
```

[Back to top](#top)

### `_shared.py`

<a id="sharedpy"></a>

```python
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

def ratio(n: int, d: int) -> float:
    return (n / d) if d else 0.0

def title_name(value: str | None) -> str | None:
    if not value: return None
    s = str(value).strip().lower()
    if not s: return None
    parts = re.split(r"([ -])", s)
    def fix(tok: str) -> str:
        t = tok.capitalize()
        if t.startswith("O'") and len(t) > 2: t = "O'" + t[2:].capitalize()
        if t.startswith("Mc") and len(t) > 2: t = "Mc" + t[2:].capitalize()
        return t
    return "".join(fix(p) if p not in {" ", "-"} else p for p in parts)
```

[Back to top](#top)

### `__init__.py`

<a id="initpy"></a>

```python
# Marks src/ade_config/ as a Python package.
```

[Back to top](#top)
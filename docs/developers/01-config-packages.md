# Config Packages — quick tour & how it runs

<a id="top"></a>

An ADE **config package** is a small, installable Python project (**`ade_config`**) that teaches the engine how to read messy spreadsheets and write a clean, consistent workbook. You write straightforward Python functions; the engine streams the spreadsheet once to find the real table bounds, **materializes each table** (it’s small), calls your functions, and emits telemetry (`events.ndjson`) that captures each decision.

## Clickable config package example

* **my-config/**

  * **[pyproject.toml](#pyprojecttoml)** — packaging metadata (installable; `src/` layout)
  * **src/**

    * **ade_config/** — runtime package the engine imports

      * **[manifest.json](#manifestjson)** — engine defaults, columns model, hooks
      * **[config.env](#configenv)** *(optional)* — environment knobs (e.g., `DATE_FMT`)
      * **[_shared.py](#sharedpy)** — tiny helpers (names, dates, numbers)
      * **[column_detectors/](#columndetectors)** — one file per **canonical field**

        * **[member_id.py](#memberidpy)** — ID mapping → normalize → validate
        * **[full_name.py](#fullnamepy)** — multi‑field transform (`→ first_name`, `last_name`)
        * **[first_name.py](#firstnamepy)**, **[last_name.py](#lastnamepy)**
        * **[email.py](#emailpy)**, **[department.py](#departmentpy)**, **[join_date.py](#joindatepy)**, **[amount.py](#amountpy)**
      * **[row_detectors/](#rowdetectors)** — row‑by‑row “is this header or data?” voters

        * **[header.py](#headerpy)**, **[data.py](#datapy)**
      * **[hooks/](#hooks)** — lifecycle touches

        * **[on_run_start.py](#onrunstartpy)**, **[after_mapping.py](#aftermappingpy)**, **[before_save.py](#beforesavepy)**, **[on_run_end.py](#onrunendpy)**
      * **[**init**.py](#initpy)** — marks the package

[Back to top](#top)

---

## Core Concepts

Think of an ADE **config package** as a set of tiny functions the engine calls while it reads a spreadsheet.

1. **Stream once → find the table.**

   The engine reads each sheet **row by row** and calls your row detectors (`row_detectors/*.py`). Those `detect_*` functions return small scores like “this looks like a **header**” or “**data**.” From those labels, the engine finds the table’s **start**, **end**, and **header row** (trimming empty space).

2. **Materialize the table (it’s small).**

   With bounds known, the engine loads just that region into memory as:

   ```text
   table = {
     "headers": list[str],          # normalized header names
     "rows":    list[list[Any]]     # 2D array; one list per data row
   }
   ```

3. **Map raw columns to your fields.**

   For each column, the engine calls your column detectors (`column_detectors/<field>.py`). Each `detect_*` receives:

   * `header` — the column’s header text
   * `column_values_sample` — a small, representative slice of that column (size is **configurable** in `manifest.json`)
   * `column_values` — the entire column (already built once; no extra copying)
   * `table` — the whole table, if context helps
     Each `detect_*` returns a tiny **score** for *its* field. The engine sums scores and assigns the best‑scoring field to the column. If enabled in the manifest, **unmatched** columns are appended on the far right with a prefix like `raw_Amount`.

4. **(Optional) Transform & validate — row by row.**

   Still inside each column file:

   * `transform()` (if present) can **normalize** a value or even fill **multiple fields** for that row (e.g., `full_name → first_name + last_name`).
   * `validate()` (if present) returns a list of **issues** for that row (e.g., “missing member_id”).
     These run **after mapping** and only affect the **current row**.

5. **Hooks let you modify whole objects at the right time.**

   Hooks are **completely optional**. They let you extend behavior without touching the engine. The four you’ll use most:

   ### `on_run_start(run)` → return **None**

   Runs once at the beginning. Use it to log or load small reference data.

   ```python
   # hooks/on_run_start.py
   def on_run_start(*, run_id: str, manifest: dict, env: dict | None = None, logger=None, **_):
       if logger: logger.info("run_start id=%s locale=%s", run_id, (env or {}).get("LOCALE", "n/a"))
       return None
   ```

   See: [`on_run_start.py`](#onrunstartpy)

   ### `after_mapping(table)` → return the **table**

   Runs after columns are mapped and **before** transforms/validators. You get the **whole table** and can mutate it: fix headers, reorder or drop columns, massage values. Return the **same `table`** (possibly changed).

   ```python
   # hooks/after_mapping.py
   def after_mapping(*, table: dict, logger=None, **_):
       # Example: rename "Work Email" -> "Email"
       table["headers"] = ["Email" if str(h).strip().lower()=="work email" else h for h in table["headers"]]
       return table
   ```

   See: [`after_mapping.py`](#aftermappingpy)

   ### `before_save(workbook)` → return the **workbook**

   Runs right before writing to disk. You get the **actual OpenPyXL `Workbook`** and can do project‑level polish: rename sheets, freeze panes, add a “Summary,” or style the normalized range as an Excel table. Return the **workbook**.

   ```python
   # hooks/before_save.py
   from openpyxl.utils import get_column_letter
   from openpyxl.worksheet.table import Table, TableStyleInfo

   def before_save(*, workbook, **_):
       ws = workbook.active
       ws.title = "Normalized"
       ws.freeze_panes = "A2"
       # Optional: style as an Excel table
       ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
       tbl = Table(displayName="NormalizedTable", ref=ref)
       tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
       ws.add_table(tbl)
       return workbook
   ```

   See: [`before_save.py`](#beforesavepy)

   ### `on_run_end(...)` → return **None**

   Runs once at the end. Perfect for logging a summary or exporting metrics via telemetry.

   ```python
   # hooks/on_run_end.py
   def on_run_end(*, tables=None, logger=None, **_):
       total_tables = len(tables or [])
       if logger: logger.note("run_end", tables=total_tables)
       return None
   ```

   See: [`on_run_end.py`](#onrunendpy)

6. **Everything is auditable.**

   Every detector score, mapping choice, transform delta, and validation issue is recorded in the telemetry stream (`events.ndjson`) so you can explain any result.

---

### One tiny detector to make it concrete

Here’s a single `detect_*` that prefers the **sample** (fast) and only reads the **full** column if a decision is borderline. Notice the tiny return shape.

```python
# column_detectors/email.py
import re
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)

def detect_value_shape(
    *,
    field_name: str,
    header: str | None,
    column_values_sample: list,
    column_values: tuple,
    table: dict,
    **_
) -> float | dict:
    # Fast path: decide from column_values_sample
    hits = sum(1 for v in column_values_sample if v and EMAIL.match(str(v)))
    ratio = hits / max(1, len(column_values_sample))
    score = 0.7 * ratio

    # If borderline, refine using column_values (already built once)
    if 0.4 <= score < 0.6:
        hits_full = sum(1 for v in column_values if v and EMAIL.match(str(v)))
        score = max(score, 0.8 * (hits_full / max(1, len(column_values))))

    return {field_name: round(score, 2)}
```

[Back to top](#top)

---

## Engine call signatures

All ADE entrypoints are invoked with **keyword arguments only**. Accept a trailing `**_` so your functions stay compatible with future context the engine might pass along.

### Row detectors (`row_detectors/*.py`)

```python
def detect_*(
    *,
    run,
    state,
    row_index: int,
    row_values: list,
    input_file_name: str | None,
    logger,
    **_,
) -> float | dict:
    ...
```

- `run` — metadata for this run (run/workspace/config IDs, sheet info, etc.).
- `state` — mutable dict that all detectors/transforms/validators share; great for caching derived info.
- `row_index` — 1-based row number as streamed from the sheet.
- `row_values` — raw cell values from that spreadsheet row.
- `input_file_name` — basename of the current source file.
- `logger` — run-scoped `logging.Logger`.
- Return a float for the detector’s default label (set `DEFAULT_LABEL`/`DEFAULT_ROW_LABEL` or inferred from the module name), or a dict mapping labels to deltas when influencing multiple labels. The legacy `"scores"` wrapper is no longer accepted.

### Column detectors (`column_detectors/<field>.py`)

```python
def detect_*(
    *,
    run,
    state,
    extracted_table,
    input_file_name: str | None,
    column_index: int,
    header: str | None,
    column_values: list,
    column_values_sample: list,
    manifest,
    logger,
    **_,
) -> float | dict:
    ...
```

- `extracted_table` — `ExtractedTable` for context (header + rows + source metadata). Also provided as `raw_table`/`unmapped_table` for backward compatibility.
- `input_file_name` — basename of the source file (also available via `extracted_table.source_file.name`).
- `column_index` — 1-based index into `extracted_table.header_row`.
- `header` — cleaned header text or `None`.
- `column_values_sample` — stratified slice of the column (size chosen in the manifest); use this first for quick scoring.
- `column_values` — list containing the entire column; only touch if absolutely needed (already materialized once).
- `manifest`, `run`, `state`, `logger` — same as above.
- Return either a float (applies to this field) or a dict of deltas (can influence multiple fields).

### Column transforms (`transform()` inside `column_detectors/<field>.py`)

```python
def transform(
    *,
    run,
    state,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    logger,
    **_,
) -> dict | None:
    ...
```

- `value` — current cell value for `field_name`.
- `row` — mutable dict of canonical fields for the current row; add/update values here.
- Return a dict of updates (merged into `row`) or `None` to leave things untouched.
- `run`, `state`, `row_index`, `logger` — same as earlier.

### Validators (`validate()` inside `column_detectors/<field>.py`)

```python
def validate(
    *,
    run,
    state,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_meta: dict | None,
    logger,
    **_,
) -> list[dict]:
    ...
```

- `field_meta` — manifest metadata for the field (can be `None` for synthetic fields).
- `value` — the current canonical value for `field_name` (after any transforms).
- `row` — the full canonical row (fields → values) so you can make cross-field checks.
- Return a list of issue dicts (e.g., `{"row_index": row_index, "code": "required_missing", ...}`) or an empty list if the value is fine.
- `run`, `state`, `row_index`, `value`, `row`, `logger` — same meanings as above.

### Hooks (`hooks/*.py`)

```python
def run(
    *,
    run,
    state,
    input_file_name: str | None,
    manifest,
    tables=None,
    workbook=None,
    result=None,
    stage,
    logger,
    **_,
) -> object | None:
    ...
```

- `input_file_name` — basename of the file being processed.
- `tables` — varies by stage (`ExtractedTable`, `MappedTable`, or `NormalizedTable`).
- `workbook` — provided during `on_before_save`.
- `result` — provided during `on_run_end`.
- Return a modified object where applicable (see Script API docs) or `None` to leave things unchanged.

[Back to top](#top)

---

## `pyproject.toml`

<a id="pyprojecttoml"></a>

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ade-config-membership"
version = "1.9.0"
description = "ADE configuration: detectors, row-level transforms, validators, and hooks"
readme = "README.md"
requires-python = ">=3.14"
authors = [{ name = "Data Quality Team", email = "dq@example.com" }]
license = { text = "Proprietary" }

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

---

## `src/ade_config/manifest.json`

<a id="manifestjson"></a>

```jsonc
{
  // Lock the script API contract for your config code
  "config_script_api_version": "1",

  "engine": {
    "defaults": {
      // Column detectors get this many representative values (head/mid/tail)
      "detector_sample_size": 64,

      // Mapping confidence gate (best score must be >= this to auto-map)
      "mapping_score_threshold": 0.35,

      // Soft runtime guardrails (tweak as needed)
      "timeout_ms": 180000,
      "memory_mb": 384
    },

    "writer": {
      // Engine writes normalized rows in order
      "mode": "row_streaming",

      // Keep unmatched columns visible (added to the right)
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

  // The engine will import these hook modules and call the functions by name
  "hooks": {
    "on_run_start":  [{ "script": "hooks/on_run_start.py" }],
    "after_mapping": [{ "script": "hooks/after_mapping.py" }],
    "before_save":   [{ "script": "hooks/before_save.py" }],
    "on_run_end":    [{ "script": "hooks/on_run_end.py" }]
  },

  // Normalized columns (order = output column order)
  "columns": {
    "order": ["member_id","full_name","first_name","last_name","email","department","join_date","amount"],
    "meta": {
      "member_id":  { "label":"Member ID", "required":true,  "script":"column_detectors/member_id.py",
                      "synonyms":["member id","member#","id (member)","customer id","client id"], "type_hint":"string" },

      "full_name":  { "label":"Full Name", "required":false, "script":"column_detectors/full_name.py",
                      "synonyms":["full name","name","employee name"], "type_hint":"string" },

      "first_name": { "label":"First Name", "required":true,  "script":"column_detectors/first_name.py",
                      "synonyms":["first name","given name","fname"], "type_hint":"string" },

      "last_name":  { "label":"Last Name", "required":true,  "script":"column_detectors/last_name.py",
                      "synonyms":["last name","surname","family name","lname"], "type_hint":"string" },

      "email":      { "label":"Email", "required":true,      "script":"column_detectors/email.py",
                      "synonyms":["email","e-mail","email address"], "type_hint":"string" },

      "department": { "label":"Department", "required":false, "script":"column_detectors/department.py",
                      "synonyms":["dept","division","team","org"], "type_hint":"string",
                      "allowed":["Sales","Support","Engineering","HR","Finance","Marketing","Operations"] },

      "join_date":  { "label":"Join Date", "required":false, "script":"column_detectors/join_date.py",
                      "synonyms":["join date","start date","hire date","onboarded"], "type_hint":"date" },

      "amount":     { "label":"Amount", "required":false, "script":"column_detectors/amount.py",
                      "synonyms":["amount","total","payment","fee","charge"], "type_hint":"number" }
    }
  }
}
```

[Back to top](#top)

---

## `src/ade_config/config.env` (optional)

<a id="configenv"></a>

```dotenv
LOCALE=en-CA
DATE_FMT=%Y-%m-%d
AMOUNT_DECIMALS=2
FUTURE_DATE_GRACE_DAYS=7

DEPT_CANONICAL=Sales;Support;Engineering;HR;Finance;Marketing;Operations
DEPT_SYNONYMS=sls=Sales,tech support=Support,eng=Engineering,dev=Engineering,acct=Finance,acctg=Finance,mktg=Marketing,ops=Operations
```

[Back to top](#top)

---

## `src/ade_config/_shared.py`

<a id="sharedpy"></a>

```python
"""
Tiny, deterministic helpers shared across detectors/transforms/validators.
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# ---------- Text / names ----------

def title_name(value: str | None) -> str | None:
    """Title-case a name while preserving common prefixes (O', Mc, etc.)."""
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

# ---------- Dates ----------

EXCEL_EPOCH = datetime(1899, 12, 30)
DATE_FORMATS = ["%Y-%m-%d","%m/%d/%Y","%d/%m/%Y","%b %d, %Y","%d %b %Y","%Y%m%d"]

def parse_date_to_iso(value, preferred_fmt: str | None = None) -> str | None:
    """Return YYYY-MM-DD from an Excel serial or common string formats; None if unknown."""
    if value in (None, ""): return None
    if isinstance(value, (int, float)):  # Excel serial number
        try: return (EXCEL_EPOCH + timedelta(days=float(value))).strftime("%Y-%m-%d")
        except Exception: return None
    s = str(value).strip()
    if preferred_fmt:
        try: return datetime.strptime(s, preferred_fmt).strftime("%Y-%m-%d")
        except Exception: pass
    for fmt in DATE_FORMATS:
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception: continue
    return None

# ---------- Numbers / currency ----------

CURRENCY_SYMBOLS = {"$", "£", "€", "¥", "₹"}

def to_decimal(raw) -> Decimal | None:
    """Parse currency-like strings to Decimal; None if not parseable."""
    if raw in (None, ""): return None
    s = str(raw).strip()
    for sym in CURRENCY_SYMBOLS: s = s.replace(sym, "")
    s = s.replace(",", "")
    if s.startswith("(") and s.endswith(")"): s = "-" + s[1:-1]  # (123.45) → -123.45
    try: return Decimal(s)
    except InvalidOperation: return None

def quantize_decimal(value: Decimal, decimals: int) -> Decimal:
    q = Decimal(10) ** -decimals
    return value.quantize(q, rounding=ROUND_HALF_UP)
```

[Back to top](#top)

---

## `src/ade_config/row_detectors/`

<a id="rowdetectors"></a>

### `header.py`

<a id="headerpy"></a>

```python
"""
Each detect_* runs for every streamed row.
Return tiny score deltas; the engine sums and labels rows as header/data.
"""
from __future__ import annotations

DEFAULT_LABEL = "header"

def detect_text_density(*, row_values: list, **_) -> float:
    """
    Rows with mostly strings are good header candidates.
    """
    cells = [c for c in row_values if c not in (None, "")]
    if not cells:
        return 0.0
    strings = sum(isinstance(c, str) for c in cells)
    ratio = strings / len(cells)
    return 0.7 if ratio >= 0.7 else (0.3 if ratio >= 0.5 else 0.0)

def detect_position_bias(*, row_index: int, **_) -> float:
    """
    Early rows are more likely to be the header (soft boost).
    """
    return 0.4 if row_index <= 3 else (0.2 if row_index <= 6 else 0.0)
```

[Back to top](#top)

### `data.py`

<a id="datapy"></a>

```python
from __future__ import annotations

DEFAULT_LABEL = "data"

def detect_numeric_presence(*, row_values: list, **_) -> float:
    """
    Data rows often contain at least one numeric cell.
    """
    nums = sum(str(v).replace(".", "", 1).isdigit() for v in row_values if v not in (None, ""))
    return +0.4 if nums >= 1 else 0.0

def detect_not_header_like(*, row_values: list, **_) -> float:
    """
    Penalize rows that look header-like (mostly strings).
    """
    non_blank = [v for v in row_values if v not in (None, "")]
    if not non_blank:
        return 0.0
    strings = sum(isinstance(v, str) for v in non_blank)
    ratio = strings / len(non_blank)
    return -0.2 if ratio >= 0.8 else 0.0
```

[Back to top](#top)

---

## `src/ade_config/column_detectors/`

<a id="columndetectors"></a>

> **How column detectors are called:** For each raw column in the materialized table, the engine calls every `detect_*` in the **target field’s** file and **adds** their scores. Use **`column_values_sample`** first for speed; only use **`column_values`** (full list) if your rule truly needs it. You can also peek at **`table_data`** if context helps.

**Common kwargs for all `detect_*` in this folder:**

* `field_name: str` — the field for this file (e.g., `"email"`).
* `field_meta: dict` — this field’s manifest entry (labels, synonyms, hints).
* `header: str | None` — cleaned header text.
* `column_values_sample: list` — stratified sample of column values (size from manifest).
* `column_values: list | None` — the full column list (shared, zero‑copy).
* `table_data: dict` — the whole table (`{"headers": [...], "rows": [[...], ...]}`).
* Plus `manifest`, `env`, `logger`, `column_index` (1‑based), etc.

**Return shape:** a float for this field or a dict of deltas (no `"scores"` wrapper).

---

### `member_id.py`

<a id="memberidpy"></a>

```python
from __future__ import annotations
import re

ID = re.compile(r"^[A-Za-z0-9]{6,12}$")

def _normalize(raw) -> str | None:
    if raw in (None, ""): return None
    s = "".join(ch for ch in str(raw) if ch.isalnum()).upper()
    return s or None

def detect_header_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_) -> dict:
    """
    Strong, cheap signal from header synonyms in the manifest.
    """
    score = 0.0
    if header:
        h = header.strip().lower()
        hits = sum(1 for syn in (field_meta.get("synonyms") or []) if syn in h)
        score = min(0.9, 0.6 * hits)
    return {field_name: score}

def detect_value_shape(
    *,
    column_values_sample: list,
    column_values: list | None = None,
    field_name: str,
    **_
) -> dict:
    """
    Prefer column_values_sample; escalate to full column only if borderline and available.
    """
    if not column_values_sample:
        return {field_name: 0.0}
    sample_hits = sum(bool(ID.match(_normalize(v) or "")) for v in column_values_sample)
    ratio = sample_hits / max(1, len(column_values_sample))
    score = round(0.6 * ratio, 2)

    if 0.4 <= score < 0.6 and column_values is not None:
        hits = sum(bool(ID.match(_normalize(v) or "")) for v in column_values)
        ratio = hits / max(1, len(column_values))
        score = max(score, round(0.7 * ratio, 2))

    return {field_name: score}

# --- After mapping (row-by-row) ---

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    """Normalize to uppercase alphanumerics."""
    if value in (None, ""): return None
    norm = _normalize(value)
    return {"member_id": norm} if norm else None

def validate(*, row_index: int, field_name: str, value, row: dict, field_meta: dict, **_) -> list[dict]:
    """Required + shape checks."""
    issues = []
    if field_meta.get("required", False) and (value in (None, "")):
        issues.append({"row_index": row_index, "code": "required_missing", "severity": "error",
                       "message": f"{field_name} is required."})
    if value not in (None, "") and not ID.match(str(value)):
        issues.append({"row_index": row_index, "code": "invalid_format", "severity": "error",
                       "message": f"{field_name} must be 6–12 alphanumeric chars"})
    return issues
```

[Back to top](#top)

---

### `full_name.py`

<a id="fullnamepy"></a>

```python
from __future__ import annotations
import re
from ade_config._shared import title_name

NAMEISH = re.compile(r"^[A-Za-z][A-Za-z' -]{0,99}$")
HINTS   = ("full name","name","employee name")

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        score = min(0.9, 0.6 * sum(1 for s in HINTS if s in h))
    return {field_name: score}

def detect_value_shape(*, column_values_sample: list, field_name: str, **_) -> dict:
    hits = sum(1 for v in column_values_sample if v not in (None, "") and NAMEISH.match(str(v).strip()))
    ratio = hits / max(1, len(column_values_sample))
    return {field_name: round(0.6 * ratio, 2)}

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    """Split full_name into first_name / last_name while also normalizing full_name."""
    if value in (None, ""): return None
    full = title_name(str(value))
    if not full: return None
    parts = [p for p in full.replace("  ", " ").split(" ") if p]
    first = parts[0] if parts else None
    last  = parts[-1] if len(parts) > 1 else None
    return {"full_name": full, "first_name": first, "last_name": last}

def validate(*, row_index: int, field_name: str, value, row: dict, **_) -> list[dict]:
    return []  # keep permissive; first/last enforce required on their own
```

[Back to top](#top)

---

### `first_name.py`

<a id="firstnamepy"></a>

```python
from ade_config._shared import title_name

HINTS = ("first name","given name","fname")

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        score = min(0.9, 0.6 * sum(1 for s in HINTS if s in h))
    return {field_name: score}

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    return {"first_name": title_name(value)} if value not in (None, "") else None

def validate(*, row_index: int, field_name: str, value, row: dict, field_meta: dict, **_) -> list[dict]:
    if field_meta.get("required", False) and (value in (None, "")):
        return [{"row_index": row_index,"code":"required_missing","severity":"error","message":"First name is required"}]
    return []
```

[Back to top](#top)

---

### `last_name.py`

<a id="lastnamepy"></a>

```python
from ade_config._shared import title_name

HINTS = ("last name","surname","family name","lname")

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        score = min(0.9, 0.6 * sum(1 for s in HINTS if s in h))
    return {field_name: score}

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    return {"last_name": title_name(value)} if value not in (None, "") else None

def validate(*, row_index: int, field_name: str, value, row: dict, field_meta: dict, **_) -> list[dict]:
    if field_meta.get("required", False) and (value in (None, "")):
        return [{"row_index": row_index,"code":"required_missing","severity":"error","message":"Last name is required"}]
    return []
```

[Back to top](#top)

---

### `email.py`

<a id="emailpy"></a>

```python
import re

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
HINTS = ("email","e-mail","email address")
COMMON_FIXES = {"gmial.com":"gmail.com","gamil.com":"gmail.com","outlok.com":"outlook.com"}

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        if any(s in h for s in HINTS): score = 0.85
    return {field_name: score}

def detect_value_shape(
    *,
    column_values_sample: list,
    column_values: list | None = None,
    field_name: str,
    **_
) -> dict:
    # Sample first (fast path)
    sample_hits = sum(bool(EMAIL.match(str(v))) for v in column_values_sample if v not in (None, ""))
    sample_ratio = sample_hits / max(1, len(column_values_sample))
    score = round(0.7 * sample_ratio, 2)

    # If borderline and full list is available, refine using full column
    if 0.4 <= score < 0.6 and column_values is not None:
        hits = sum(bool(EMAIL.match(str(v))) for v in column_values if v not in (None, ""))
        ratio = hits / max(1, len(column_values))
        score = max(score, round(0.8 * ratio, 2))

    return {field_name: score}

def transform(*, row_index: int, field_name: str, value, row: dict, **_) -> dict | None:
    if value in (None, ""): return None
    s = str(value).strip().lower()
    if "@" in s:
        local, _, domain = s.partition("@")
        s = f"{local}@{COMMON_FIXES.get(domain, domain)}"
    return {"email": s}

def validate(*, row_index: int, field_name: str, value, row: dict, field_meta: dict, **_) -> list[dict]:
    if value in (None, ""):  # required check handled elsewhere if needed
        return []
    if not EMAIL.match(str(value)):
        return [{"row_index": row_index,"code":"invalid_format","severity":"error","message":"Email must look like user@domain.tld"}]
    return []
```

[Back to top](#top)

---

### `department.py`

<a id="departmentpy"></a>

```python
def _load_allowed(manifest: dict, env: dict | None) -> tuple[set[str], dict[str,str]]:
    env = env or {}
    allowed = set((env.get("DEPT_CANONICAL") or "").split(";")) if env.get("DEPT_CANONICAL") else \
              set(manifest["columns"]["meta"]["department"].get("allowed", []))
    synonyms: dict[str,str] = {}
    for kv in (env.get("DEPT_SYNONYMS") or "").split(","):
        k, _, v = kv.partition("=")
        if k.strip() and v.strip():
            synonyms[k.strip().lower()] = v.strip()
    return allowed, synonyms

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        if any(s in h for s in ("dept","department","division","team","org")):
            score = 0.7
    return {field_name: score}

def transform(*, row_index: int, field_name: str, value, row: dict, manifest: dict, env: dict | None = None, **_) -> dict | None:
    if value in (None, ""): return None
    allowed, synonyms = _load_allowed(manifest, env)
    s = str(value).strip()
    canon = s if s in allowed else synonyms.get(s.lower(), s)
    return {"department": canon}

def validate(*, row_index: int, field_name: str, value, row: dict, manifest: dict, env: dict | None = None, **_) -> list[dict]:
    issues = []
    allowed, _ = _load_allowed(manifest, env)
    if value not in (None, "") and allowed and value not in allowed:
        issues.append({"row_index": row_index,"code":"out_of_set","severity":"warning","message":f"Unknown department: {value}"})
    return issues
```

[Back to top](#top)

---

### `join_date.py`

<a id="joindatepy"></a>

```python
from ade_config._shared import parse_date_to_iso

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        if any(s in h for s in ("join date","start date","hire date","onboarded")):
            score = 0.7
    return {field_name: score}

def transform(*, row_index: int, field_name: str, value, row: dict, env: dict | None = None, **_) -> dict | None:
    iso = parse_date_to_iso(value, preferred_fmt=(env or {}).get("DATE_FMT"))
    return {"join_date": iso} if iso else None

def validate(*, row_index: int, field_name: str, value, row: dict, env: dict | None = None, **_) -> list[dict]:
    # Optional: future-date guard
    return []
```

[Back to top](#top)

---

### `amount.py`

<a id="amountpy"></a>

```python
from decimal import Decimal
from ade_config._shared import to_decimal, quantize_decimal

def detect_header_synonyms(*, header: str | None, field_name: str, **_) -> dict:
    score = 0.0
    if header:
        h = header.strip().lower()
        if any(s in h for s in ("amount","total","payment","fee","charge")):
            score = 0.7
    return {field_name: score}

def transform(*, row_index: int, field_name: str, value, row: dict, env: dict | None = None, **_) -> dict | None:
    d = to_decimal(value)
    if d is None: return None
    decimals = int((env or {}).get("AMOUNT_DECIMALS", "2"))
    q = quantize_decimal(d, decimals)
    return {"amount": float(q)}

def validate(*, row_index: int, field_name: str, value, row: dict, **_) -> list[dict]:
    return []
```

[Back to top](#top)

---

## `src/ade_config/hooks/`

<a id="hooks"></a>

### `on_run_start.py`

<a id="onrunstartpy"></a>

```python
"""
Called once at run start. Log/setup; return None.
"""
from __future__ import annotations
from logging import Logger

def on_run_start(*, run_id: str, manifest: dict, env: dict | None = None, logger: Logger | None = None, **_) -> None:
    env = env or {}
    if logger:
        logger.info("run_start id=%s locale=%s date_fmt=%s", run_id, env.get("LOCALE","n/a"), env.get("DATE_FMT","n/a"))
    return None
```

[Back to top](#top)

---

### `after_mapping.py`

<a id="aftermappingpy"></a>

```python
"""
Whole table in, whole table out. Tweak headers/columns/values before transforms/validators.
table_data = {"headers": list[str], "rows": list[list[Any]]}
"""
from __future__ import annotations
from logging import Logger
from typing import Any, Dict, List

TableData = Dict[str, List]  # simple alias

def after_mapping(*, table: TableData, manifest: dict, env: dict | None = None, logger: Logger | None = None, **_) -> TableData:
    # Example 1: normalize a header label
    table["headers"] = [
        "Email" if (h or "").strip().lower() == "work email" else h
        for h in table["headers"]
    ]

    # Example 2: drop an all-empty "Notes" column
    try:
        idx = table["headers"].index("Notes")
        if all((len(r) <= idx) or (r[idx] in (None, "")) for r in table["rows"]):
            table["headers"].pop(idx)
            for r in table["rows"]:
                if len(r) > idx: r.pop(idx)
            if logger: logger.info("after_mapping: dropped empty 'Notes' column")
    except ValueError:
        pass

    # Example 3: optional reorder to a preferred reading order (by header labels)
    preferred = ["Member ID","Email","First Name","Last Name","Department","Join Date","Amount"]
    index = {h: i for i, h in enumerate(table["headers"])}
    if all(h in index for h in preferred):
        order = [index[h] for h in preferred]
        table["headers"] = [table["headers"][i] for i in order]
        for r in range(len(table["rows"])):
            row = table["rows"][r]
            table["rows"][r] = [row[i] if i < len(row) else None for i in order]

    return table
```

[Back to top](#top)

---

### `before_save.py`

<a id="beforesavepy"></a>

```python
"""
Polish the final workbook. Return the same Workbook instance (or a replacement).
"""
from __future__ import annotations
from logging import Logger
from openpyxl.workbook import Workbook  # type: ignore
from openpyxl.utils import get_column_letter  # type: ignore
from openpyxl.worksheet.table import Table, TableStyleInfo  # type: ignore

def before_save(*, workbook: Workbook, logger: Logger | None = None, **_) -> Workbook:
    ws = workbook.active
    if ws.title != "Normalized":
        ws.title = "Normalized"
    ws.freeze_panes = "A2"

    # Optional: Excel "structured table" styling + autosize
    if ws.max_row and ws.max_column:
        ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
        tbl = Table(displayName="NormalizedTable", ref=ref)
        tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium9", showRowStripes=True)
        ws.add_table(tbl)

        for c in range(1, ws.max_column + 1):
            letter = get_column_letter(c)
            width = max((len(str(cell.value)) for cell in ws[letter] if cell.value is not None), default=10) + 2
            ws.column_dimensions[letter].width = min(60, max(10, width))

    if logger:
        logger.info("before_save: sheet normalized, styling applied")
    return workbook
```

[Back to top](#top)

---

### `on_run_end.py`

<a id="onrunendpy"></a>

```python
"""
Summarize results via logs; return None.
"""
from __future__ import annotations
from logging import Logger
def on_run_end(*, tables=None, logger: Logger | None = None, **_) -> None:
    total_tables = len(tables or [])
    if logger:
        logger.info("on_run_end: tables=%s", total_tables)
    return None
```

[Back to top](#top)

---

## `src/ade_config/__init__.py`

<a id="initpy"></a>

```python
# Marks src/ade_config/ as a Python package.
```

[Back to top](#top)

---

### Recap (mental model)

* **Row detectors**: `row_detectors/*.py` with `detect_*` → stream rows to find table bounds.
* **Column detectors**: `column_detectors/<field>.py` with `detect_*` → receive `header`, `column_values_sample`, `column_values`, `table_data`; return a **score for your field**.
* **Transforms / validators** (optional): run **row‑by‑row after mapping** in the same column file.
* **Hooks**: `after_mapping(table) → table`, `before_save(workbook) → workbook`, `on_run_start/on_run_end → None`.
* **Unmatched columns**: appended on the right when enabled in `manifest.json` (using `unmapped_prefix`).
* **Artifact**: every detection, mapping, transform, and validation is recorded for auditability.

This layout keeps the authoring model **simple** and the runtime **fast**: sample first, full list if you need it; whole table to `after_mapping`; whole workbook to `before_save`.

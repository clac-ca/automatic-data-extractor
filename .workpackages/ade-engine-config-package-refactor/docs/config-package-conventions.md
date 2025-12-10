# ade-config (ADE Engine): Config Package Conventions

This document describes the **recommended** conventions for building an `ade-config` package for the ADE Engine architecture (registry + dynamic discovery). The core idea is simple:

> **A config package is just a normal Python package.**  
> When ADE imports it, your code **registers** Field definitions, Column/Row Detectors, Column Transforms, Column Validators, and Hooks into the engine Registry.

There is **no manifest.toml** in ADE Engine.

---

## 1) What you’re building (mental model)

An ADE config package provides six kinds of plugins:

1. **Fields**  
   The canonical output fields you want (e.g. `email`, `first_name`, `gross_wages`).

2. **Row Detectors**  
   Functions that help the engine decide which rows are header/data/blank/etc by returning score adjustments.

3. **Column Detectors**  
   Functions that help the engine decide which field a column maps to by returning score adjustments.

4. **Column Transforms**  
   Functions that normalize/clean values for a mapped field.

5. **Column Validators**  
   Functions that check values for a mapped field (reporting only).

6. **Hooks** (HookName)  
   Functions that can modify the run at specific points (e.g. patch mappings, reorder output, tweak workbook before save).

ADE imports your package, the Registry fills up, then the pipeline runs using whatever was registered.

---

## 2) Non-goals / principles

### Keep it obvious
- One file per field (recommended) so a developer can open `columns/email.py` and see everything for email.

### Keep it dynamic
- Adding a new `*.py` file under the package should “just work” without editing any centralized list.

### Keep import-time side effects minimal
- Imports should only define and register things.
- Don’t read network/files at import time. Do that inside hooks/detectors if needed.

### Keep it deterministic
- If you register multiple detectors/transforms, use `priority=` to control evaluation order. Avoid “random” ordering.

---

## 3) Recommended folder layout (convention, not a requirement)

You can place files anywhere under the package. This is the recommended “standard and intuitive” layout:

```text
src/ade_config/
  __init__.py
  meta.py                 # optional: human-readable package metadata

  common/
    __init__.py
    tokens.py             # helpers used by detectors
    patterns.py

  columns/
    __init__.py
    email.py              # field + column detectors + transform + validate (together)
    first_name.py
    last_name.py
    ...

  rows/
    __init__.py
    header.py             # row detectors related to header row detection
    data.py               # row detectors related to data rows

  hooks/
    __init__.py
    on_table_mapped.py
    on_workbook_before_save.py
````

**Why this layout works well:**

* Fast to navigate.
* Stable naming.
* Matches ADE concepts: Columns / Rows / Hooks.

---

## 4) Minimal “Hello world” config package

### 4.1 `pyproject.toml` (package identity)

```toml
[project]
name = "ade-config-dart-remittances"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "ade-engine", # or whatever the engine package name is
]

[tool.setuptools.packages.find]
where = ["src"]
```

### 4.2 `src/ade_config/__init__.py`

You can keep this empty. If you want explicitness, you can import subpackages:

```py
# Optional explicit imports (not required if engine discovery imports recursively)
from . import columns, rows, hooks  # noqa: F401
```

### 4.3 `src/ade_config/columns/email.py`

A typical “one file per column” pattern:

```py
from __future__ import annotations

import re
from ade_engine.registry.decorators import (
    column_detector,
    column_transform,
    column_validator,
    field_meta,
)
from ade_engine.registry.models import (
    ColumnDetectorContext,
    TransformContext,
    ValidateContext,
    ScorePatch,
)

# 1) Column detector(s)
@field_meta(name="email", label="Email", required=True, dtype="string", synonyms=["email", "email address", "e-mail"])  # optional metadata helper
@column_detector(field="email", priority=100)
def detect_email_header(ctx: ColumnDetectorContext) -> ScorePatch:
    # ctx.header is the column header string (may be None)
    header = (ctx.header or "").lower()

    if "email" in header or "e-mail" in header:
        # Strong match; also softly discourage confusing alternatives
        return {"email": 1.0, "work_email": 0.2, "work_phone": -0.4}

    return 0.0

@column_detector(field="email", priority=50)
def detect_email_values(ctx: ColumnDetectorContext) -> ScorePatch:
    # ctx.column_values_sample is a small sample (may be None)
    values = ctx.column_values_sample or []
    hits = 0
    for v in values:
        s = str(v or "").strip()
        if "@" in s and "." in s:
            hits += 1

    # Score based on how many samples "look like" emails
    score = min(1.0, hits / max(1, len(values)))
    return {"email": score}

# 2) Column transform (flat field→value dict per row)
@column_transform(field="email", priority=0)
def normalize_email(ctx: TransformContext):
    rows = []
    for v in ctx.values:
        rows.append({
            "email": str(v or "").strip().lower() or None,
        })
    return rows

# 3) Column validator (reporting only)
_EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")

@column_validator(field="email", priority=0)
def validate_email(ctx: ValidateContext):
    issues = []
    for row_idx, v in enumerate(ctx.values):
        s = str(v or "").strip().lower()
        if s and not _EMAIL_RE.match(s):
            issues.append({
                "passed": False,
                "message": f"Invalid email: {v}",
                "row_index": row_idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
```

**Notes:**

* You can register multiple detectors per field (header-based, value-based, etc.).
* Detectors can return a dict that boosts *multiple fields* (positive/negative). That’s a core feature.
* Field definitions are optional; if you reference a field name in detectors/transforms/validators and it was not explicitly defined, the engine will auto-create a field with default metadata. Define it explicitly only when you need labels/required/dtype/synonyms.

---

## 5) Row detectors conventions

Row detectors are typically grouped into:

* **header row detectors** (look for header-ish tokens),
* **data row detectors** (look for repeated patterns, numeric density, etc.).

Example: `src/ade_config/rows/header.py`

```py
from __future__ import annotations

from ade_engine.registry.decorators import row_detector
from ade_engine.registry.models import RowDetectorContext, ScorePatch

@row_detector(priority=100)
def detect_header_tokens(ctx: RowDetectorContext) -> ScorePatch:
    # ctx.row_values: list[Any] for the current row
    values = [str(v or "").strip().lower() for v in (ctx.row_values or [])]
    joined = " ".join(values)

    # Very naive example
    hits = sum(1 for token in ("name", "email", "address", "dob") if token in joined)
    if hits >= 2:
        return {"header": 1.0, "data": -0.5}

    return {"header": 0.0}
```

---

## 6) Hooks conventions (HookName)

Hooks are for “power-user” modifications at defined points. The most common uses:

* patch column mappings after detection,
* reorder output columns,
* modify workbook just before save.

### 6.1 Reordering columns (now that output ordering is automatic)

**Default behavior in ADE Engine:**

* mapped columns preserve **input order**
* unmapped columns are appended to the right (if enabled by engine settings)

If you want custom ordering, do it in `HookName.ON_TABLE_MAPPED`.

Example: `src/ade_config/hooks/on_table_mapped.py`

```py
from __future__ import annotations

from ade_engine.registry.decorators import hook
from ade_engine.registry.models import HookName, HookContext

@hook(HookName.ON_TABLE_MAPPED, priority=0)
def reorder_output_columns(ctx: HookContext) -> None:
    """
    Example: force a preferred ordering for the FINAL output.
    This runs after mapping, before transforms/render.
    """

    preferred = [
        "email",
        "first_name",
        "last_name",
        "member_id",
    ]

    # Sort columns in place: preferred first (if present), then the rest in current order.
    def sort_key(col) -> tuple[int, int]:
        if col.field_name in preferred:
            return (0, preferred.index(col.field_name))
        return (1, col.source_index)

    ctx.table.columns.sort(key=sort_key)
```

**Convention:** hooks should generally **mutate** the provided objects (table/workbook/mapping) and return `None`.

---

## 7) Naming conventions (make it instantly readable)

### Fields

* `snake_case` field names: `first_name`, `postal_code`, `gross_wages`
* Use human labels where appropriate: `"Gross Wages"`

### Files

* Match file name to field name for column modules:

  * `columns/first_name.py` defines `first_name`
  * `columns/gross_wages.py` defines `gross_wages`

### Function names

Registry does not *need* unique names, but humans do. Prefer:

* `detect_<field>_header`
* `detect_<field>_values`
* `transform_<field>`
* `validate_<field>`
* `on_<hook_name>` (or descriptive hook name)

---

## 8) Common helpers (recommended)

Create a small `common/` folder for shared utilities:

* tokenization (`header_tokens`)
* numeric density checks
* regex patterns
* date parsing
* phone normalization

This keeps detectors small and consistent.

Example structure:

```text
ade_config/common/
  tokens.py       # header_tokens(), normalize_header()
  stats.py        # percent_numeric(), uniqueness_ratio()
  parse.py         # parse_date(), parse_money()
```

---

## 9) How discovery works (what devs should assume)

Dev-facing rule of thumb:

> If the file is under your `ade_config` package and is importable, ADE will import it and your registrations will be picked up.

To keep things predictable:

* avoid conditional imports that hide modules,
* avoid registering based on environment at import time,
* prefer explicit `priority=` over relying on incidental import order.

---

## 10) Troubleshooting checklist

* **Nothing registers**

  * Ensure the package is importable (installed / on PYTHONPATH)
  * Ensure modules are under `ade_config/` (or whatever package name you configured)
  * Ensure you imported the correct decorators from `ade_engine.registry`

* **Conflicting fields**

  * Two modules registered the same `field(name="email", ...)`
  * Fix by keeping one canonical file per field (recommended)

* **Detectors run but mapping is weird**

  * Add `priority` to ensure the stronger heuristic wins
  * Return negative deltas for “confusable” fields when appropriate

* **Need custom output ordering**

  * Do it in `HookName.ON_TABLE_MAPPED` with `ctx.table.reorder_columns(...)`

---

## 11) Summary: the “standard” ADE Engine way

For most configs, the standard approach is:

* One file per field in `columns/`:

  * `field(...)`
  * `@column_detector` (1–3 detectors)
  * `@column_transform`
  * `@column_validator`
* A couple row detector files in `rows/`
* Optional hooks in `hooks/` for advanced behavior

That’s it—no manifest, no wiring lists, no ordering config, no module strings.

# Callable contracts (Row/Column Detectors, Transforms, Validators, Hooks)

This document defines the **stable, developer-facing contracts** for ADE Engine plugin callables.

The engine runs a fixed pipeline (extract → detect rows → detect columns → map → transform → validate → render) and calls **your functions** at specific points. Your functions should be small, composable, and **only adjust scores / values**, not “decide” outcomes.

---

## 0) Design principles

1) **One argument:** every plugin callable receives exactly **one** argument: a typed context object `ctx`.
2) **Pure by default:** detectors/transforms/validators should be deterministic and side-effect free (except reading `ctx.state` / logging).
3) **Shared state is explicit:** cross-stage communication happens through `ctx.state` (a per-run mutable dict).
4) **Scores are additive:** detectors return “score patches” (deltas), which the engine sums.
5) **Hooks are the escape hatch:** if you need to patch mappings, reorder output, call an LLM, etc., do it in a Hook.

---

## 1) Common types

### 1.1 ScorePatch (used by Row Detectors and Column Detectors)

A detector returns either:

- `float` — shorthand meaning “adjust the detector’s **default target** score”
- `dict[str, float]` — adjust multiple candidate scores at once

```py
from typing import TypeAlias

ScorePatch: TypeAlias = float | dict[str, float]
````

**Semantics**

* Keys are **candidate names**:

  * Row detectors: row labels like `"header"`, `"data"`, `"unknown"` (whatever your engine supports).
  * Column detectors: field names like `"email"`, `"first_name"`, etc.
* Values are **deltas** (can be negative).
* The engine merges patches by **adding** deltas into a running score table.

**Shorthand float behavior**

* Row detector returning a float applies to the detector’s default target (engine-defined label for that detector).
* Column detector returning a float applies to the detector’s declared `field` (set in the decorator).

Detectors should return either a float or a dict; treat missing return as a no-op.

### 1.2 TransformResult

Transforms operate on column values and return a new list (preferred) or the same list (if you choose to mutate in place).

```py
from typing import TypeAlias, Any

TransformResult: TypeAlias = list[Any]
```

### 1.3 Validation result

Validators currently return a simple `bool` (reporting-only). The engine records failures but does not drop data.  
> Note: richer “issues list” returns are an open decision in the workpackage; keep docs and code tolerant of upgrading this contract later.

---

## 2) Context objects

All callables receive a single context object. The engine owns these types and may add fields over time (non-breaking). Rule of thumb: **only use what you need** from the context.

### 2.1 RowDetectorContext

```py
from dataclasses import dataclass
from typing import Any

@dataclass
class RowDetectorContext:
    run: Any                      # engine run/session object
    state: dict[str, Any]         # per-run mutable shared dict
    sheet: Any                    # sheet handle (engine type)
    row_index: int
    row_values: list[Any]
    logger: Any
```

### 2.2 ColumnDetectorContext

```py
from dataclasses import dataclass
from typing import Any

@dataclass
class ColumnDetectorContext:
    run: Any
    state: dict[str, Any]
    sheet: Any
    column_index: int
    header: str | None
    column_values: list[Any]
    column_values_sample: list[Any]
    logger: Any
```

### 2.3 TransformContext

```py
from dataclasses import dataclass
from typing import Any

@dataclass
class TransformContext:
    run: Any
    state: dict[str, Any]
    field_name: str
    values: list[Any]
    logger: Any
```

### 2.4 ValidateContext

```py
from dataclasses import dataclass
from typing import Any

@dataclass
class ValidateContext:
    run: Any
    state: dict[str, Any]
    field_name: str
    values: list[Any]
    logger: Any
```

### 2.5 HookContext (common shape)

```py
from dataclasses import dataclass
from typing import Any

@dataclass
class HookContext:
    run: Any
    state: dict[str, Any]
    workbook: Any | None = None
    sheet: Any | None = None
    table: Any | None = None
    logger: Any | None = None
```

### 2.6 HookContext (varies by HookName)

Hooks have different contexts depending on the HookName, but all include BaseContext fields plus stage-specific objects.

Example (common pattern):

```py
from dataclasses import dataclass
from typing import Any

@dataclass
class HookContext(BaseContext):
    workbook: Any | None
    sheet: Any | None
    extracted_table: Any | None
    mapped_table: Any | None
    output_workbook: Any | None
```

The engine will define concrete hook context types per hook for better typing (recommended), but the mental model stays the same: hooks receive a context with “the thing you’re allowed to change *right now*”.

---

## 3) Row Detectors

### 3.1 Purpose

Row detectors **score row kinds** (e.g. header row vs data row) while scanning a sheet/table region.

They do not declare winners. They only return score deltas.

### 3.2 Signature

```py
from ade_engine.registry.models import RowDetectorContext, ScorePatch

def detect_something(ctx: RowDetectorContext) -> ScorePatch:
    ...
```

### 3.3 Return rules

* Return a `dict[str, float]` to adjust multiple kinds at once:

```py
return {"header": 1.0, "data": -0.5}
```

* Return a `float` to adjust only the detector’s default target kind (declared in decorator metadata):

```py
return 0.8
```

### 3.4 Example

```py
from ade_engine.registry.decorators import row_detector
from ade_engine.registry.models import RowDetectorContext, ScorePatch

COMMON_HEADER_TOKENS = {"name", "email", "address", "phone", "id"}

@row_detector(priority=50)
def detect_headerish_row(ctx: RowDetectorContext) -> ScorePatch:
    tokens = {str(v).strip().lower() for v in ctx.row_values if v is not None}
    hit = len(tokens & COMMON_HEADER_TOKENS)
    if hit >= 2:
        # boost header, slightly penalize data
        return {"header": 1.2, "data": -0.4}
    return 0.0
```

---

## 4) Column Detectors

### 4.1 Purpose

Column detectors score **which field** a column represents based on header text and cell values. They can also penalize competing fields.

### 4.2 Signature

```py
from ade_engine.registry.models import ColumnDetectorContext, ScorePatch

def detect_something(ctx: ColumnDetectorContext) -> ScorePatch:
    ...
```

### 4.3 Return rules

* Return `{"email": 1.0, "work_email": -0.2}` etc.
* Return a `float` to affect the detector’s default `field` (declared in decorator).

### 4.4 Example (your current style, cleaned up)

```py
from ade_engine.registry.decorators import column_detector
from ade_engine.registry.models import ColumnDetectorContext, ScorePatch

def header_tokens(s: str | None) -> set[str]:
    if not s:
        return set()
    return {t.strip().lower() for t in s.replace("-", " ").split() if t.strip()}

@column_detector(field="address_line1", priority=50)
def detect_address_line1_header(ctx: ColumnDetectorContext):
    tokens = header_tokens(ctx.header)
    if not tokens:
        return 0.0

    # strong signal
    if ("address" in tokens and ("line1" in tokens or "1" in tokens)):
        return {
            "address_line1": 1.0,
            "address_line2": -0.7,
            "city": -0.3,
            "postal_code": -0.3,
        }

    # weaker signal
    if "address" in tokens or "street" in tokens:
        return {"address_line1": 0.8, "city": -0.3, "postal_code": -0.3}

    return 0.0
```

---

## 5) Column Transforms

### 5.1 Purpose

Transforms rewrite values for a mapped field (normalization, parsing, redaction, standardization).

Transforms run **after mapping** (you know which field this column is).

### 5.2 Return shape (minimal)

- Column transformers return a **row-aligned list** (length = input rows).
  - Each item can be:
    - a raw value (shorthand for `{current_field: value}`), or
    - a dict of `field_name -> value`. The dict MUST include the current field; extra keys set other fields for that row.
- Cell transformers return either a raw value or that dict per cell; the wrapper assembles the row-aligned list.

### 5.3 Example

```py
import re
from ade_engine.registry.decorators import column_transform, cell_transformer
from ade_engine.registry.models import TransformContext

# Column-level: split full name while keeping original
@column_transform(field="full_name", priority=10)
def split_full_name(ctx: TransformContext):
    rows = []
    for v in ctx.values:
        first, last = None, None
        if v:
            parts = str(v).split(None, 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else None
        rows.append({
            "full_name": v,
            "first_name": first,
            "last_name": last,
        })
    return rows

# Cell-level sugar: per-cell, same dict shape
@cell_transformer(field="phone", priority=50)
def normalize_phone_cell(ctx: TransformContext, row_idx: int, value):
    if value is None:
        return {"phone": None}
    digits = re.sub(r"\\D+", "", str(value))
    return {
        "phone": digits or None,
    }
```

**Guidelines**

* Prefer returning a new list (clear, testable).
* Use `ctx.state` only for shared caches (e.g. compiled regex, lookups).

---

## 6) Column Validators

### 6.1 Purpose

Validators produce reportable quality signals. They do not drop data.

### 6.2 Return shape (simple and explicit)

- Return a **validation result dict** or a **list of them**. Keys:
  - `passed: bool` (required)
  - `message: str | None` (why it failed)
  - `row_index: int | None` (optional pointer to the offending row)
  - `column_index: int | None` (optional pointer to the input column)
  - `value: Any | None` (optional offending value)
- Engine rule: any item with `passed is False` becomes an issue; `passed is True` emits nothing.

### 6.3 Column-level example (points to specific cells)

```py
import re
from ade_engine.registry.decorators import column_validator
from ade_engine.registry.models import ValidateContext

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@column_validator(field="email", priority=50)
def validate_emails(ctx: ValidateContext):
    issues = []
    for row_idx, v in enumerate(ctx.values):
        if v and not EMAIL_RE.match(str(v).strip()):
            issues.append({
                "passed": False,
                "message": f"Invalid email: {v}",
                "row_index": row_idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
```

### 6.4 Cell-level ergonomics (`@cell_validator`)

`@cell_validator(field=...)` lets you write per-cell logic; it still returns the same dict shape, one per cell, and the wrapper aggregates them.

```py
from ade_engine.registry.decorators import cell_validator
from ade_engine.registry.models import ValidateContext

@cell_validator(field="email", priority=50)
def validate_email_cell(ctx: ValidateContext, row_idx: int, value):
    if value and "@" not in str(value):
        return {
            "passed": False,
            "message": f"Invalid email: {value}",
            "row_index": row_idx,
            "column_index": getattr(ctx, "column_index", None),
            "value": value,
        }
    return {"passed": True}
```

---

## 7) Hooks (HookName)

### 7.1 Purpose

Hooks are called at well-defined points in the pipeline to:

* patch mapping results,
* reorder output columns,
* add additional sheets,
* format workbook,
* call external systems, etc.

### 7.2 Signature

```py
from ade_engine.registry.models import HookContext

def my_hook(ctx: HookContext) -> None:
    ...
```

Hooks should return `None` and mutate objects in the context.

### 7.3 Example (reorder columns in ON_TABLE_MAPPED)

This matches the new simplification: **engine no longer stores output order**. If you care about output order, do it here.

```py
from ade_engine.registry.decorators import hook
from ade_engine.registry.models import HookName, HookContext

@hook(HookName.ON_TABLE_MAPPED, priority=50)
def reorder_output_columns(ctx: HookContext) -> None:
    table = ctx.table
    if table is None:
        return

    preferred = ["email", "first_name", "last_name"]

    def sort_key(col):
        if col.field_name in preferred:
            return (0, preferred.index(col.field_name))
        return (1, col.source_index)

    table.columns.sort(key=sort_key)
```

---

## 8) Naming & organization conventions

* **Functions must have unique names within a module** (standard Python rule).
* You can define **multiple detectors/transforms/validators/hooks in the same file** (recommended when they’re related).
* Prefer descriptive names like:

  * `detect_email_header`
  * `detect_headerish_row`
  * `normalize_phone`
  * `validate_emails`
  * `on_table_mapped_patch_mapping`
* Ordering is controlled by decorator `priority`, not file order.

---

## 9) Error handling expectations

* Detectors should be defensive: return `0.0` / `{}` when unsure.
* The engine will normalize and continue when a detector returns:

  * `None` → no-op
  * `float` → `{default_target: float}`
  * `dict` → used directly (unknown keys ignored or warned; engine decides)
* Hooks are powerful: prefer failing fast on hook exceptions (config bug) unless the engine is explicitly set to “warn and continue”.

---

## 10) Quick reference (cheat sheet)

```py
# Row Detector
def fn(ctx: RowDetectorContext) -> ScorePatch: ...

# Column Detector
def fn(ctx: ColumnDetectorContext) -> ScorePatch: ...

# Column Transform
def fn(ctx: TransformContext) -> list[Any]: ...

# Column Validator
def fn(ctx: ValidateContext) -> bool: ...

# Hook
def fn(ctx: HookContext) -> None: ...
```

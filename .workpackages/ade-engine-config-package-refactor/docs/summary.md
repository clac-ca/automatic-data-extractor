## 1) The mental model (what ADE fundamentally does)

### The pipeline in plain terms

1. **Read workbook** (sheet by sheet).
2. **Row detection**: run all **Row Detectors** on each row to score row types (header/data/etc). Pick the header row (and table region).
3. **Column detection**: for each column, run all **Column Detectors** to score which **Field** it represents (email, first_name, etc).
4. **Mapping**: choose the winning field per column (with tie-break rules).
5. **Hook**: `ON_TABLE_MAPPED` (optional) gives you the mapped table so you can patch mapping, reorder output, call LLM, etc.
6. **Transform**: run **Column Transforms** on mapped fields.
7. **Validate**: run **Column Validators** (reporting-only, doesn’t wipe data).
8. **Render output workbook**.
9. **Hook**: `ON_WORKBOOK_BEFORE_SAVE` (optional) final chance to modify the workbook.

### The “score patch” idea (core to detectors)

Detectors don’t just say “yes/no”. They adjust scores.

* A detector may return:

  * a **float**: “adjust the score of the current candidate field”
  * or a **dict[str, float]**: “boost this field and penalize others”

This allows “mutual exclusion” logic (e.g., if it smells like `address_line1`, it probably isn’t `city`).

---

## 2) What we’re changing (decisions locked in)

### A) Move from TOML manifest → registry + discovery (code-first)

**Old:** TOML manifest listed columns + module strings + order
**New:** The config package is a normal Python package. It registers:

* Fields
* Column Detectors
* Row Detectors
* Column Transforms
* Column Validators
* Hooks

Registration happens via decorators/helpers when modules are imported.

✅ Result: no duplicate “source of truth”; adding a `.py` file is the workflow.

---

### B) Remove the need to store output column order in config

**New default output behavior:**

* Keep **mapped columns in the same order they appear in the input sheet**
* If enabled, **append unmapped columns** to the far right (prefixed)
* Mapping conflicts use **highest-score-wins**; score ties are resolved by the engine setting `mapping_tie_resolution` (`leftmost` default, or `drop_all` to leave ties unmapped).

If someone wants a custom order, they do it in a Hook (typically `ON_TABLE_MAPPED`).

✅ Result: you eliminate a whole class of config/UI complexity.

---

### C) Move engine behavior toggles into `ade_engine.settings` (pydantic-settings)

Settings like:

* `append_unmapped_columns`
* `unmapped_prefix`

…become **engine settings** with clear precedence:

1. init kwargs / programmatic overrides (highest)
2. env vars
3. `.env`
4. `ade_engine.toml` (or similar)
5. defaults

✅ Result: standard behavior control, fewer manifest knobs.

---

### D) Standardize terminology and naming

Canonical terms:

* **Row Detectors**
* **Column Detectors**
* **Column Transforms**
* **Column Validators**
* **Hooks** (use `HookName`, not `EventName`)

✅ Result: the architecture reads like a typical plugin system.

---

## 3) The ADE Engine spec (how it works)

### 3.1 Registry: the bridge between engine and config package

The registry holds “what exists” and provides deterministic ordering.

Key rules:

* Everything is registered under one registry instance.
* Discovery imports modules → decorators register callables.
* Deterministic execution order:

  * sort by `(priority desc, module_path asc, qualname asc)`.

### 3.2 Callable contracts

We keep **callables**. They’re the simplest, most standard plugin surface:

* easy to author
* easy to test
* easy to version (via contexts)
* easy for your “VS Code in browser” workflow

We make them *feel* standard by passing **context objects** instead of a giant arg list.

---

## 4) Code examples (engine-side)

### 4.1 Core types: score patch + contexts

```py
# apps/ade-engine/src/ade_engine/registry/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal

ScorePatch = float | dict[str, float]

class HookName(str, Enum):
    ON_WORKBOOK_START = "on_workbook_start"
    ON_SHEET_START = "on_sheet_start"
    ON_TABLE_DETECTED = "on_table_detected"
    ON_TABLE_MAPPED = "on_table_mapped"
    ON_TABLE_WRITTEN = "on_table_written"
    ON_WORKBOOK_BEFORE_SAVE = "on_workbook_before_save"

@dataclass(frozen=True)
class FieldDef:
    name: str
    label: str
    dtype: Literal["string", "number", "date", "bool"] = "string"
    required: bool = False
    synonyms: list[str] = field(default_factory=list)

@dataclass
class RowDetectorContext:
    run: Any
    state: dict[str, Any]
    sheet: Any
    row_index: int
    row_values: list[Any]
    logger: Any

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

@dataclass
class TransformContext:
    run: Any
    state: dict[str, Any]
    field_name: str
    values: list[Any]
    logger: Any

@dataclass
class ValidateContext:
    run: Any
    state: dict[str, Any]
    field_name: str
    values: list[Any]
    logger: Any

@dataclass
class HookContext:
    run: Any
    state: dict[str, Any]
    workbook: Any | None = None
    sheet: Any | None = None
    table: Any | None = None
    logger: Any | None = None
```

### 4.2 Registry + normalization helpers

```py
# apps/ade-engine/src/ade_engine/registry/registry.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .models import FieldDef, HookName, ScorePatch

@dataclass(frozen=True)
class RegisteredFn:
    kind: str
    fn: Callable[..., Any]
    priority: int
    module: str
    qualname: str
    field: str | None = None
    hook_name: HookName | None = None

class Registry:
    def __init__(self) -> None:
        self.fields: dict[str, FieldDef] = {}
        self.row_detectors: list[RegisteredFn] = []
        self.column_detectors: list[RegisteredFn] = []
        self.column_transforms: list[RegisteredFn] = []
        self.column_validators: list[RegisteredFn] = []
        self.hooks: dict[HookName, list[RegisteredFn]] = {h: [] for h in HookName}

    def _sort_key(self, r: RegisteredFn) -> tuple[int, str, str]:
        return (-r.priority, r.module, r.qualname)

    def finalize(self) -> None:
        self.row_detectors.sort(key=self._sort_key)
        self.column_detectors.sort(key=self._sort_key)
        self.column_transforms.sort(key=self._sort_key)
        self.column_validators.sort(key=self._sort_key)
        for h in self.hooks:
            self.hooks[h].sort(key=self._sort_key)

    def register_field(self, field: FieldDef) -> None:
        if field.name in self.fields:
            raise ValueError(f"Duplicate field registered: {field.name}")
        self.fields[field.name] = field

    def normalize_patch(self, current_field: str, patch: ScorePatch) -> dict[str, float]:
        if isinstance(patch, (int, float)):
            return {current_field: float(patch)}
        return {k: float(v) for k, v in patch.items()}
```

### 4.3 Decorators + “current registry” (discovery-friendly)

We use a controlled global (via `contextvars`) so decorators can register without manual wiring.

```py
# apps/ade-engine/src/ade_engine/registry/current.py
from __future__ import annotations
from contextvars import ContextVar
from .registry import Registry

_current: ContextVar[Registry | None] = ContextVar("ade_registry_current", default=None)

def set_current_registry(reg: Registry) -> None:
    _current.set(reg)

def get_current_registry() -> Registry:
    reg = _current.get()
    if reg is None:
        raise RuntimeError("No active Registry. Did you load the config package?")
    return reg
```

```py
# apps/ade-engine/src/ade_engine/registry/decorators.py
from __future__ import annotations
from typing import Any, Callable

from .current import get_current_registry
from .models import FieldDef, HookName
from .registry import RegisteredFn

def define_field(*, name: str, label: str, dtype: str = "string",
                 required: bool = False, synonyms: list[str] | None = None) -> FieldDef:
    """Optional helper: explicitly declare field metadata. Not required to register a field; the engine will auto-create fields when referenced by name."""
    field = FieldDef(name=name, label=label, dtype=dtype, required=required, synonyms=synonyms or [])
    get_current_registry().register_field(field)
    return field

def row_detector(*, priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        reg = get_current_registry()
        reg.row_detectors.append(RegisteredFn(
            kind="row_detector", fn=fn, priority=priority,
            module=fn.__module__, qualname=fn.__qualname__,
        ))
        return fn
    return deco

def column_detector(*, field: str, priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        reg = get_current_registry()
        reg.column_detectors.append(RegisteredFn(
            kind="column_detector", fn=fn, priority=priority,
            module=fn.__module__, qualname=fn.__qualname__, field=field,
        ))
        return fn
    return deco

def column_transform(*, field: str, priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        reg = get_current_registry()
        reg.column_transforms.append(RegisteredFn(
            kind="column_transform", fn=fn, priority=priority,
            module=fn.__module__, qualname=fn.__qualname__, field=field,
        ))
        return fn
    return deco

def column_validator(*, field: str, priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        reg = get_current_registry()
        reg.column_validators.append(RegisteredFn(
            kind="column_validator", fn=fn, priority=priority,
            module=fn.__module__, qualname=fn.__qualname__, field=field,
        ))
        return fn
    return deco

def hook(hook_name: HookName, *, priority: int = 0) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        reg = get_current_registry()
        reg.hooks[hook_name].append(RegisteredFn(
            kind="hook", fn=fn, priority=priority,
            module=fn.__module__, qualname=fn.__qualname__, hook_name=hook_name,
        ))
        return fn
    return deco
```

### 4.4 Discovery: import modules under config package

```py
# apps/ade-engine/src/ade_engine/registry/discovery.py
from __future__ import annotations
import importlib
import pkgutil
from types import ModuleType

def import_all(package_name: str) -> None:
    pkg = importlib.import_module(package_name)
    if not hasattr(pkg, "__path__"):
        # single module package
        return

    for modinfo in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        importlib.import_module(modinfo.name)
```

---

## 5) Settings (engine-side) with env + optional TOML

```py
# apps/ade-engine/src/ade_engine/settings.py
from __future__ import annotations
from pathlib import Path
import tomllib
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

def _toml_source(settings: BaseSettings) -> dict[str, Any]:
    path = Path("ade_engine.toml")
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    # convention: [ade_engine] section
    return data.get("ade_engine", {})

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADE_ENGINE_",
        env_file=".env",
        extra="ignore",
    )

    # config package import path
    config_package: str = "ade_config"

    # output writer behavior
    append_unmapped_columns: bool = True
    unmapped_prefix: str = "raw_"

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # precedence: init > env > .env > toml > defaults
        return (init_settings, env_settings, dotenv_settings, _toml_source, file_secret_settings)
```

Example `.env`:

```bash
ADE_ENGINE_APPEND_UNMAPPED_COLUMNS=true
ADE_ENGINE_UNMAPPED_PREFIX=raw_
ADE_ENGINE_CONFIG_PACKAGE=ade_config
```

Example `ade_engine.toml`:

```toml
[ade_engine]
append_unmapped_columns = true
unmapped_prefix = "raw_"
config_package = "ade_config"
```

---

## 6) Config package (ADE Engine) — what developers write

Recommended structure (but flexible):

```text
ade_config/
  __init__.py
  columns/
    email.py
    first_name.py
  rows/
    header.py
    data.py
  hooks/
    on_table_mapped.py
```

### 6.1 A column file: detectors + transform + validator in one place

```py
# ade_config/columns/email.py
import re
from ade_engine.registry.decorators import column_detector, column_transform, column_validator, field_meta
from ade_engine.registry.models import ColumnDetectorContext, TransformContext, ValidateContext, ScorePatch

def _tokenize(s: str | None) -> set[str]:
    if not s:
        return set()
    return set(re.findall(r"[a-z0-9]+", s.lower()))

# (separator in this snippet; real code would omit this line)

@field_meta(name="email", label="Email", required=True, dtype="string", synonyms=["email", "email address", "e-mail"])
@column_detector(field="email", priority=50)
def detect_email_header(ctx: ColumnDetectorContext) -> ScorePatch:
    t = _tokenize(ctx.header)
    if "email" in t or "e-mail" in t:
        # boost email; slightly penalize things that commonly collide
        return {"email": 1.0, "work_email": -0.2}
    return 0.0

@column_transform(field="email", priority=0)
def normalize_email(ctx: TransformContext):
    rows = []
    for v in ctx.values:
        rows.append({
            "email": str(v).strip().lower() if v is not None else None,
        })
    return rows

@column_validator(field="email", priority=0)
def validate_email(ctx: ValidateContext):
    issues = []
    for row_idx, v in enumerate(ctx.values):
        if v is None or v == "":
            continue
        if "@" not in str(v):
            issues.append({
                "passed": False,
                "message": f"Invalid email: {v}",
                "row_index": row_idx,
                "column_index": getattr(ctx, "column_index", None),
                "value": v,
            })
    return issues or {"passed": True}
```

### 6.2 A row detector file

```py
# ade_config/rows/header.py
import re
from ade_engine.registry.decorators import row_detector
from ade_engine.registry.models import RowDetectorContext, ScorePatch

def _tokens(row: list[object]) -> set[str]:
    joined = " ".join("" if v is None else str(v) for v in row).lower()
    return set(re.findall(r"[a-z0-9]+", joined))

@row_detector(priority=10)
def detect_header_row(ctx: RowDetectorContext) -> ScorePatch:
    t = _tokens(ctx.row_values)
    # crude example: headers often contain these
    hits = len(t.intersection({"email", "name", "first", "last", "address"}))
    if hits >= 2:
        return {"header": 1.0, "data": -0.3}
    return {"header": 0.0}
```

---

## 7) Hooks (and how reordering works now)

We removed “explicit output order in config”. If someone wants output ordering, they do it in a hook.

### Example: reorder columns in `ON_TABLE_MAPPED`

Assume the engine exposes a `table` object with a `columns` list where each column has `.field_name` and `.source_index`.

```py
# ade_config/hooks/on_table_mapped.py
from ade_engine.registry.decorators import hook
from ade_engine.registry.models import HookName, HookContext

@hook(HookName.ON_TABLE_MAPPED, priority=0)
def reorder_output_columns(ctx: HookContext) -> None:
    table = ctx.table
    if table is None:
        return

    desired = ["email", "first_name", "last_name"]

    def sort_key(col) -> tuple[int, int]:
        # desired fields first, in desired order; then everything else keeps stable order
        if col.field_name in desired:
            return (0, desired.index(col.field_name))
        return (1, col.source_index)

    table.columns.sort(key=sort_key)
```

That’s it: the engine will render output columns in `table.columns` order.

---

## 8) How the engine uses the registry in each stage (simple terms)

### Load phase

1. Create `Registry()`
2. Set it as “current” (so decorators know where to register)
3. Import the config package recursively (`import_all(settings.config_package)`)
4. `registry.finalize()` to sort everything deterministically

### Row detection

* For each row:

  * run every registered Row Detector
  * normalize patches → accumulate scores per row-type label (e.g. `"header"`, `"data"`)
* choose header row

### Column detection + mapping

* For each column:

  * run detectors (some detectors are specific to a field; others can still return multi-field patches)
  * accumulate scores per field
* pick winning field for the column

### Hooks

* On `ON_TABLE_MAPPED`, pass the mapped table object:

  * allow patching mapping
  * allow reordering output columns
  * allow calling external logic (LLM, rules engines)

### Transform + validate

* For each mapped field:

  * apply transforms registered for that field (priority order)
  * run validators registered for that field (priority order)

### Render output (new default)

* **Mapped** columns: keep **input column order** (unless hook reorders)
* **Unmapped** columns: append right if `settings.append_unmapped_columns` (prefix with `settings.unmapped_prefix`)

---

## 9) Practical outcomes (why this is simpler)

* No TOML manifest to maintain or keep in sync.
* No module string wiring.
* No “column ordering UI” requirement.
* Developers add files naturally in the GUI editor; discovery just finds them.
* Hook-based escape hatch for advanced behavior (like ordering).
* Settings use a standard Python ecosystem solution (`pydantic-settings`).

If you want, I can also provide a “mini end-to-end” pseudo-implementation of the mapping accumulator (how scores are combined, how ties break, how duplicates are handled) so the spec is fully executable.

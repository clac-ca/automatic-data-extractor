# docs/registry-spec.md

## Purpose

The **Registry** is the single source of truth that tells ADE **what capabilities exist** in a config package:

- **Fields** (the canonical output targets like `email`, `first_name`, …)
- **Row Detectors** (score which rows are headers vs data)
- **Column Detectors** (score which field each column represents)
- **Column Transforms** (normalize values for a mapped field)
- **Column Validators** (validate values for reporting)
- **Hooks** (custom logic at defined points in the pipeline)

The engine imports the config package, the config package registers things into the registry, and the pipeline runs everything from the registry—no TOML manifest wiring, no module-string switches.

This spec defines the registry’s data model, registration API, ordering rules, and error handling.

---

## Glossary

- **Field**: A canonical output column (e.g. `email`). Fields are what column mapping resolves to.
- **RowKind**: The classification target for row detection (e.g. `HEADER`, `DATA`).
- **Detector**: A callable that returns score adjustments (“patches”) used by the engine to pick a winner.
- **ScorePatch**: A detector output: either a `float` (shorthand) or `{name: delta}` dict.
- **HookName**: A named hook point in the engine lifecycle (e.g. `ON_TABLE_MAPPED`).

---

## Registry lifecycle (engine-side)

1. Engine creates a new empty `Registry`.
2. Engine activates that registry for registration (recommended: `contextvars`).
3. Engine imports all modules under the chosen config package (e.g., via `pkgutil.walk_packages`).
4. Decorators and `field(...)` calls register definitions into the active registry.
5. Engine freezes the registry (no further registration).
6. Pipeline reads registry content to run detectors/transforms/validators/hooks.

**Important:** The registry is **per-run**. Do not rely on module globals that persist across runs.

---

## Determinism requirements

To keep behavior stable and predictable:

- Discovery order should not affect outcomes; the registry sorts definitions.
- The registry MUST execute detectors/transforms/validators/hooks deterministically:
  - primary sort: `priority` (higher runs first)
  - secondary sort: module path (lexicographic)
  - tertiary sort: function qualname (lexicographic)

---

## Core types (normative)

### 1) ConfigMeta (optional)

Config packages MAY register metadata.

**Fields:**
- `name: str` (display name)
- `description: str | None`
- `version: str | None` (config package version; not the engine version)
- `script_api_version: int` (used for compatibility gates if you want them)

**Rules:**
- At most one `ConfigMeta` MAY be registered. If multiple are registered, the engine MUST raise `RegistryError`.

---

### 2) FieldDef

A FieldDef describes a canonical field the engine can map to.

**Fields:**
- `name: str` (required; unique key like `"email"`)
- `label: str | None` (display label like `"Email"`)
- `dtype: str` (default `"string"`; engine may treat as metadata)
- `required: bool` (default `False`)
- `synonyms: list[str]` (default `[]`; helpful for UI/authoring, detectors can use it)
- `description: str | None`

**Rules:**
- `name` MUST be unique within a registry. Duplicate names MUST raise `DuplicateFieldError`.
- Fields are the only valid mapping targets. Column detector patches referencing unknown field names MUST be ignored and SHOULD emit an issue/warning.
- Engine MAY auto-create a FieldDef with default metadata when a detector/transform/validator references an unknown field name; explicit `define_field` is only required when custom metadata (label/required/dtype/synonyms) is needed.

**Non-goal:** FieldDef does *not* define output ordering. ADE Engine output ordering is an engine concern.

---

### 3) RowKind

Row detectors score among a small, engine-defined set of row kinds.

**Baseline built-ins (current default):**
- `RowKind.HEADER`
- `RowKind.DATA`

> Open item from the workpackage: finalize the canonical row labels set. Keep docs/code flexible to add more kinds, but treat the above two as the minimum supported today.

---

### 4) HookName

Hooks run at defined hook points.

**Required built-ins:**
- `HookName.ON_WORKBOOK_START`
- `HookName.ON_SHEET_START`
- `HookName.ON_TABLE_DETECTED`
- `HookName.ON_TABLE_MAPPED`
- `HookName.ON_TABLE_WRITTEN`
- `HookName.ON_WORKBOOK_BEFORE_SAVE`

---

### 5) ScorePatch

Detectors return either:

- `float` — shorthand for “apply this delta to the detector’s declared default target”
- `dict[str, float]` — explicit patch affecting one or many targets

**For Row Detectors:**
- dict keys MUST correspond to row kind names (e.g. `"header"`, `"data"`) OR a stable serialized form (see below).
- recommended: normalize keys to `RowKind` values internally (engine-side)

**For Column Detectors:**
- dict keys MUST correspond to registered `FieldDef.name` values.

**Rules:**
- Missing/empty patches MUST be treated as “no change.”
- Non-finite values (`NaN`, `inf`) MUST be treated as invalid and ignored (and SHOULD emit an issue).
- Unknown keys MUST be ignored (and SHOULD emit an issue).

---

### 6) ValidationResult (validators)

Validators return either a single ValidationResult dict or a list of them.

Required key:
- `passed: bool`

Optional keys:
- `message: str | None`
- `row_index: int | None`
- `column_index: int | None`
- `value: Any | None`

Rules:
- Any item with `passed is False` becomes a reported issue (using message/row/col/value when provided).
- Items with `passed is True` emit no issue.
- Validators MAY return a list to report multiple failures; engine flattens lists.
- Invalid shapes MUST raise a clear error during normalization.

---

## Definition records (what the registry stores)

The registry stores “definition records” (callable + metadata) for each capability.

### RowDetectorDef

**Fields:**
- `fn: RowDetectorCallable`
- `row_kind: RowKind` (default target for float returns)
- `priority: int = 0`
- `enabled: bool = True`
- `description: str | None`
- `registration_index: int` (assigned by registry)

### ColumnDetectorDef

**Fields:**
- `fn: ColumnDetectorCallable`
- `field: str` (default target for float returns; MUST be a registered field name)
- `priority: int = 0`
- `enabled: bool = True`
- `description: str | None`
- `registration_index: int`

### ColumnTransformDef

**Fields:**
- `fn: ColumnTransformCallable`
- `field: str` (MUST be registered)
- `priority: int = 0`
- `enabled: bool = True`
- `registration_index: int`

**Return rules (transform callables):**
- Column transforms must return a row-aligned list (length == input rows).
- Each item may be:
  - a raw value (shorthand for `{current_field: value}`), or
  - a dict of `field_name -> value` where the current field key MUST be present; additional keys set other fields for that row.
- `cell_transformer` is sugar that returns the same shapes per cell and aggregates to the row-aligned list.
- If multiple transforms set the same field for the same row, deterministic priority ordering applies; later wins (and SHOULD log the overwrite).

### ColumnValidatorDef (Column Validators)

**Fields:**
- `fn: ColumnValidatorCallable`
- `field: str` (MUST be registered)
- `priority: int = 0`
- `enabled: bool = True`
- `registration_index: int`

### HookDef

**Fields:**
- `fn: HookCallable`
- `hook_name: HookName`
- `priority: int = 0`
- `enabled: bool = True`
- `registration_index: int`

---

## Registration API (config-package side)

The config package registers definitions using helper functions and decorators from `ade_engine.registry`.

### Active registry requirement

Registration MUST occur only when an “active registry” exists (set by the engine during discovery).

- If a config module is imported without an active registry, registration MUST raise a clear `RegistryNotActiveError`
  (this prevents silent “it imported but didn’t register anything” failures).

---

### 1) Registering Row Detectors

Row detectors are registered via `@row_detector(...)`.

```py
from ade_engine.registry.decorators import row_detector
from ade_engine.registry.models import RowDetectorContext, RowKind, ScorePatch

@row_detector(row_kind=RowKind.HEADER, priority=50)
def detect_headerish(ctx: RowDetectorContext) -> ScorePatch:
    ...
```

* `row_kind` sets the default target for float patches.  
* Return type: `ScorePatch` (`float` shorthand → applies to `row_kind`).

---

### 3) Registering Column Detectors

Column detectors are registered via `@column_detector(field=..., priority=...)`.

```py
from ade_engine.registry.decorators import column_detector, field_meta
from ade_engine.registry.models import ColumnDetectorContext, ScorePatch

@field_meta(name="email", label="Email", dtype="string")  # optional metadata helper (auto-creates/updates FieldDef)
@column_detector(field="email", priority=100)
def detect_email_header(ctx: ColumnDetectorContext) -> ScorePatch:
    ...
```

* `field` is required and must match a registered `FieldDef.name`.  
* `float` shorthand patches apply to that `field`; dict patches may boost/penalize multiple fields. Unknown field keys are ignored (warn).

---

### 4) Registering Column Transforms

```py
from ade_engine.registry.decorators import column_transform
from ade_engine.registry.models import TransformContext

@column_transform(field="email", priority=0)
def normalize_email(ctx: TransformContext) -> list[object]:
    ...
```

* Transforms run after mapping on mapped columns for the given field.  
* Multiple transforms per field are allowed; run order is deterministic (priority, module, qualname).

---

### 5) Registering Column Validators

```py
from ade_engine.registry.decorators import column_validator
from ade_engine.registry.models import ValidateContext

@column_validator(field="email", priority=0)
def validate_email(ctx: ValidateContext):
    return {"passed": True}  # or a list of result dicts with passed/message/row/col/value
```

* Validators are reporting-only.  
* Return type: one validation result dict or a list of them (`passed` required; optional `message/row_index/column_index/value`).  
* `@cell_validator` is a convenience decorator that runs per cell but registers as a column validator; it returns the same dict shape and the wrapper aggregates per-column.

---

### 6) Registering Hooks

```py
from ade_engine.registry.decorators import hook
from ade_engine.registry.models import HookName, HookContext

@hook(HookName.ON_TABLE_MAPPED, priority=10)
def reorder_output(ctx: HookContext) -> None:
    ...
```

* Hooks receive a stage-specific context and should mutate in place.  
* Deterministic order: priority desc, module asc, qualname asc.

---

### 7) ScorePatch normalization (engine-side)

The registry (or a shared helper) should normalize detector returns with:

```py
normalize_score_patch(current_target: str, patch: ScorePatch) -> dict[str, float]
```

Rules:
* `float` → `{current_target: float(patch)}`
* `dict` → cast values to float, drop NaN/inf, drop unknown keys
* `None`/empty → `{}` (no-op)

---

### 8) Finalizing the registry

After discovery/imports:

1. Validate registrations (duplicate fields → error; detectors referencing unknown fields → warn/skip).  
2. Sort all buckets deterministically (priority desc, module asc, qualname asc).  
3. Freeze the registry to prevent further mutation during the run.
4. Mapping stage uses highest-score-wins; any score ties for the same field are resolved via engine setting `mapping_tie_resolution` (`leftmost` | `drop_all`).

---

### 9) Error handling expectations

* Duplicate `FieldDef.name` ⇒ fail fast (`DuplicateFieldError`).  
* Unknown field names in detector patches ⇒ ignore and emit issue/warning.  
* Registration without an active registry ⇒ `RegistryNotActiveError`.  
* Non-finite scores (`NaN`, `inf`) ⇒ ignore and emit issue/warning.

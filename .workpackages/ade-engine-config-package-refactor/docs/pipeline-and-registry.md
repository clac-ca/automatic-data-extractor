````md
# docs/ade-engine/pipeline-and-registry.md

## Overview

In ADE Engine, the **config package doesn’t describe what to run** (no TOML manifest, no module strings).  
Instead, the config package **registers capabilities in code** (Row Detectors, Column Detectors, Column Transforms, Column Validators, Hooks) and the ade-engine pipeline **asks the Registry what exists** at each stage.

Think of it like this:

- **ade-config** = “Here are the detectors/transforms/validators/hooks I provide.”
- **Registry** = the in-memory catalog of those capabilities.
- **Pipeline** = “At step X, run all items of type Y from the Registry.”

This makes everything dynamic and discoverable, while keeping the runtime behavior deterministic.

---

## Core idea (simple mental model)

1) **Discovery step imports the config package** (and all its modules).  
2) Import-time decorators register callables into a **Registry**.  
3) The pipeline runs through its stages and pulls the right callables from the Registry at each stage.  
4) Callables receive a context object and return:
   - **Detectors**: a score adjustment (`float` or `{name: delta, ...}`)
   - **Transform**: transformed values
   - **Validate**: pass/fail (reporting only)
   - **Hooks**: side effects / patches / in-place mutations

---

## What the Registry contains

At runtime, the Registry is the *single source of truth* for “what can the config do?”

Typical buckets:

- **Fields**
  - `FieldDef(name, label, synonyms, required, dtype, ...)`

- **Row Detectors**
  - Used to classify rows (most importantly: find header row / table boundaries)

- **Column Detectors**
  - Used to score which field a column best matches

- **Column Transform**
  - Used after mapping to normalize/transform cell values

- **Column Validators**
  - Used after transform to validate values (reporting only)

- **Hooks** (keyed by `HookName`)
  - `ON_WORKBOOK_START`, `ON_SHEET_START`, `ON_TABLE_DETECTED`,
    `ON_TABLE_MAPPED`, `ON_TABLE_WRITTEN`, `ON_WORKBOOK_BEFORE_SAVE`

**Key property:** the pipeline doesn’t need a manifest to know what to run.  
It just calls things like `registry.column_detectors()` or `registry.hooks(HookName.ON_TABLE_MAPPED)`.

---

## Discovery: how the Registry gets populated

### 1) Engine locates a config package
The engine is given (or resolves) something like:
- `ADE_ENGINE_CONFIG_PACKAGE=ade_config` (import path)

### 2) Engine imports everything under that package
Discovery walks modules under the package and imports them (e.g. via `pkgutil.walk_packages`).

### 3) Decorators register callables
As each module imports, decorated callables run registration:

- `@row_detector(...)`
- `@column_detector(...)`
- `@column_transform(...)`
- `@column_validator(...)`
- `@hook(HookName....)`

This is the whole wiring model. No central list.

### Determinism note
Discovery order is not relied upon for behavior. The Registry sorts callables deterministically (e.g. priority + module path + function name). So behavior is stable even if files move.

---

## Pipeline stages and where the Registry is used

Below is the full pipeline flow, showing **exactly where** registry items are used.

### Stage 0 — Initialize run

**Inputs:**
- Workbook file path / bytes
- Engine `Settings` (pydantic-settings)
- Config package import path

**Work:**
- Load `Settings` (safe defaults if nothing is set)
- Discover + build `Registry`
- Create per-run `state: dict[str, Any]` (shared scratchpad)

**Registry usage:**
- None yet (just created)

**Hook usage:**
- `HookName.ON_WORKBOOK_START`
  - Used for run-level initialization (e.g. set state flags, load external reference data)

---

### Stage 1 — Sheet traversal + table extraction

**Work:**
- Iterate sheets
- Extract candidate tables / regions (your existing extractor stays, but simplified where possible)

**Registry usage:**
- None for extraction itself (unless you choose to allow extraction plugins later)

**Hook usage:**
- `HookName.ON_SHEET_START`
- `HookName.ON_TABLE_DETECTED` (once a candidate table exists)

---

### Stage 2 — Row detection (find header row / row roles)

**Goal:**
Decide which row in the extracted table is the header row (and/or classify rows as `header`, `data`, `unknown`, etc.).

**How it works (conceptually):**
For each candidate row `r`:
1) Initialize a scoreboard for row labels (e.g. `header`, `data`, `unknown`)
2) Run all Row Detectors from the Registry
3) Aggregate their score patches into the scoreboard
4) Pick the row label winner for that row
5) Finally pick the best row index for the `header` role

**Detector return type:**
- `float` → applies to the “current label” (when detector is label-specific)
- `dict[str, float]` → can boost one label and penalize others

**Registry usage:**
- `registry.row_detectors()` → returns all row detectors (sorted deterministically)

**Output:**
- `header_row_index`
- optionally: other row role decisions (start of data, footer rows, etc.)

---

### Stage 3 — Column detection (score each column against fields)

**Goal:**
For each column in the detected table, compute a score per field and decide which field it most likely represents.

**How it works (conceptually):**
For each column `c`:
1) Build a scoreboard `{field_name: score}` initialized to 0 for all known fields
2) For each Column Detector from the Registry:
   - Call detector with context (header cell, samples, full column values, etc.)
   - Normalize result to a `{field_name: delta}` patch
   - Apply patch to the scoreboard (including negative deltas to penalize competing fields)
3) After all detectors run, you have a final per-field score for the column

**Registry usage:**
- `registry.fields()` → list of known fields
- `registry.column_detectors()` → returns all column detectors (sorted deterministically)

**Output:**
- `column_scores[c] = {field_name: score, ...}`

---

### Stage 4 — Mapping (choose best field per column)

**Goal:**
Turn `column_scores` into a concrete mapping: which input column maps to which field (or unmapped).

**Mapping policy (finalized):**
1) For each input column, pick the top scoring field if its score ≥ threshold (highest-score-wins).  
2) Enforce one-to-one mapping. If multiple columns tie for the same field with equal top score, resolve via `settings.mapping_tie_resolution` (`leftmost` default; `drop_all` leaves all tied columns unmapped).  
3) Required fields:
   - if required fields are missing, record issues (or allow hook to patch mapping)

**Registry usage:**
- `registry.fields()` provides `required`/metadata
- (optionally) `registry.mapping_policy` if you later make mapping pluggable

**Output:**
- `mapping`: `{input_column_index -> field_name | None}` plus metadata (scores, reasons)

---

### Stage 5 — Hook: ON_TABLE_MAPPED (the “escape hatch”)

**Goal:**
Give config authors a single powerful point to:
- patch mapping decisions
- reorder output columns (if they really want to)
- call out to external services (LLM, APIs) to infer unmapped columns
- add derived columns
- drop columns, rename output headers, etc.

**Hook usage:**
- `HookName.ON_TABLE_MAPPED`

**Registry usage:**
- `registry.hooks(HookName.ON_TABLE_MAPPED)`

**Important:** This hook is where “custom column ordering” lives now.  
By default, ade-engine does *not* require or store a column order.

---

### Stage 6 — Column Transform (normalize values for mapped fields)

**Goal:**
For each mapped field, run its Column Transform (if any) on the column values.

**Behavior:**
- Transform runs after mapping so it knows the field.
- Transform returns a **row-aligned list** (length == input rows). Each item can be:
  - a raw value (shorthand for `{current_field: value}`), or
  - a dict of `field_name -> value` that MUST include the current field; extra keys set additional fields for that row (e.g., splitting `full_name` into `first_name`/`last_name`).

**Registry usage:**
- `registry.column_transforms(field_name)` → returns transforms for that field (often 0..1)

**Output:**
- `transformed_values[field_name] = [...]`, plus any additional fields set via dict items.

---

### Stage 7 — Column Validation (reporting only)

**Goal:**
For each mapped field, run validators (if any) to report quality.

**Rules:**
- Validation does **not** delete data.
- Validators return a validation result dict (or list) with `passed` and optional `message/row_index/column_index/value`; any `passed=False` is reported as an issue.

**Registry usage:**
- `registry.column_validators(field_name)` → returns validators for that field

**Output:**
- issues/validation report attached to run result

---

### Stage 8 — Render output workbook

**Goal:**
Create output workbook/table with mapped + optionally unmapped columns.

**New default output ordering (simplification):**
1) **Mapped columns** appear in the **same order as the input columns**  
2) If `Settings.append_unmapped_columns` is true:
   - append all unmapped columns on the far right
   - prefix their headers with `Settings.unmapped_prefix` (e.g. `raw_`)

**Registry usage:**
- Usually none required here (unless you use field metadata for output headers)

**Hook usage:**
- `HookName.ON_TABLE_WRITTEN` (post-write adjustments at table level)

---

### Stage 9 — Hook: ON_WORKBOOK_BEFORE_SAVE

**Goal:**
Last chance to modify the final workbook before saving.

**Use cases:**
- formatting
- adding summary tabs
- freezing panes
- applying styles
- final reorder across sheets

**Hook usage:**
- `HookName.ON_WORKBOOK_BEFORE_SAVE`

---

## How shared `state` works

A single `state: dict[str, Any]` is created per run and passed to:
- all detectors
- transforms
- validators
- hooks

This is the simplest way to support “remember something from earlier and use it later,” e.g.:
- remember which sheet had the best table
- store an LLM-produced mapping patch
- cache reference data

**Rule of thumb:**  
Use `state` for cross-stage scratch data; put structured outputs in typed pipeline objects.

---

## Tie-breakers and determinism

Determinism matters for trust and debugging. ADE Engine should be deterministic by default.

### Detector ordering
Detectors (and hooks) are run in a stable order, e.g.:
1) `priority` (higher first)
2) module path (lexicographic)
3) function qualname (lexicographic)

### Score ties (mapping)
If two fields tie for a column:
- prefer a deterministic tie-break (e.g. field name lexicographic)
- or prefer “required” fields if tie
- but keep it documented and consistent

### Duplicate field mapping
Default: enforce uniqueness.
- If multiple columns map to the same field, keep the strongest one, others become unmapped.
- Hooks can override.

---

## Error handling policy (recommended)

Keep the engine stable and the debugging clear:

- **Detector exceptions**
  - record an issue with detector name and context
  - continue (unless you explicitly want fail-fast)

- **Hook exceptions**
  - recommended fail-fast (hooks are for advanced customization; better to surface errors)

- **Transform/Validate exceptions**
  - record issues; continue where possible

Whatever policy you choose, make it explicit and consistent in code + docs.

---

## Minimal pseudocode (end-to-end)

```python
settings = Settings.load()
registry = discover_and_build_registry(config_package=settings.config_package)

state = {}

run_hooks(registry, HookName.ON_WORKBOOK_START, ctx=WorkbookStartCtx(..., state=state))

wb = read_workbook(...)
for sheet in wb.sheets:
    run_hooks(registry, HookName.ON_SHEET_START, ctx=SheetStartCtx(..., state=state))

    tables = extract_tables(sheet)

    for table in tables:
        run_hooks(registry, HookName.ON_TABLE_DETECTED, ctx=TableDetectedCtx(table=table, state=state))

        header_row = detect_header_row(table, registry.row_detectors(), state)
        column_scores = score_columns(table, header_row, registry.column_detectors(), registry.fields(), state)
        mapping = choose_mapping(column_scores, registry.fields(), settings)

        run_hooks(registry, HookName.ON_TABLE_MAPPED, ctx=TableMappedCtx(table=table, mapping=mapping, state=state))

        values = apply_transforms(table, mapping, registry, state)
        issues = run_validators(values, mapping, registry, state)

        out_table = render(values, mapping, settings, input_order=True, append_unmapped=settings.append_unmapped_columns)
        run_hooks(registry, HookName.ON_TABLE_WRITTEN, ctx=TableWrittenCtx(out_table=out_table, state=state))

run_hooks(registry, HookName.ON_WORKBOOK_BEFORE_SAVE, ctx=WorkbookBeforeSaveCtx(workbook=out_wb, state=state))
save(out_wb)
````

---

## Debuggability: what to log

To keep this system intuitive for developers:

* Which config package was loaded + how many modules imported
* Registry summary: counts of fields/detectors/transforms/validators/hooks
* Row detection:

  * chosen header row index + top contributing detectors
* Column detection:

  * per-column top-N field scores (or at least winner + score)
* Final mapping decisions:

  * duplicates resolved, required fields missing
* Hook invocations:

  * which hooks ran and in what order
  * if a hook patched mapping, log a diff

---

## Why this design stays simple

* The engine has one question at each stage: **“What does the Registry say I should run?”**
* The config author’s job is one thing: **register callables** that operate on clear contexts.
* Output ordering is no longer a config problem:

  * default behavior is predictable
  * special ordering is a hook concern

This is the simplest structure that still supports the full “score patch + hooks + transforms + validation” model.

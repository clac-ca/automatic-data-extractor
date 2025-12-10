> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

### A) Decisions locked in (simplifications)

* [x] **Remove explicit output column ordering** — output keeps **mapped columns in input order**; optionally **append unmapped columns to far right**.
* [x] **Move writer toggles into ade-engine Settings** — e.g. `append_unmapped_columns`, `unmapped_prefix` loaded via `.env`/env/TOML with safe defaults.

### B) New architecture: registry + discovery

* [x] Add **Registry** core (models + decorators + ordering rules). (Task: [01-registry-core](tasks/01-registry-core.md))
  * [x] Add **Config discovery** (import all modules under config package to auto-register detectors/transforms/validators/hooks). (Task: [02-config-discovery](tasks/02-config-discovery.md))
  * [x] Define and document **Callable contracts** (contexts + return types) for:

  * [x] Row Detectors (Task: [03-callable-row-detectors](tasks/03-callable-row-detectors.md))
  * [x] Column Detectors (field defs optional; engine auto-creates fields on first reference; optional `@field_meta` for metadata — see docs/registry-spec.md and docs/config-package-conventions.md) (Task: [04-callable-column-detectors](tasks/04-callable-column-detectors.md))
  * [x] Column Transforms (row-aligned list; each item is a raw value or a dict of `field -> value` that MUST include the current field; extra keys set other fields; `cell_transformer` sugar returns the same shape per cell — see docs/callable-contracts.md and docs/pipeline-and-registry.md) (Task: [05-callable-column-transforms](tasks/05-callable-column-transforms.md))
  * [x] Column Validators (return a validation result dict with `passed` and optional `message/row_index/column_index/value`, or a list of them; `cell_validator` sugar aggregates per-cell — see docs/callable-contracts.md and docs/registry-spec.md) (Task: [06-callable-column-validators](tasks/06-callable-column-validators.md))
  * [x] Hooks (HookName) (Task: [07-callable-hooks](tasks/07-callable-hooks.md))

### C) Pipeline refactor (no backwards compatibility)

* [x] Refactor row detection to use Registry row detectors (remove legacy loader usage). (Task: [08-pipeline-row-detection](tasks/08-pipeline-row-detection.md))
* [x] Refactor column detection + mapping to use Registry fields + column detectors. (Task: [09-pipeline-column-detection-mapping](tasks/09-pipeline-column-detection-mapping.md))
* [x] Refactor transform step to use Registry column transforms. (Task: [10-pipeline-transform](tasks/10-pipeline-transform.md))
* [x] Refactor validation step to use Registry column validators (reporting only). (Task: [11-pipeline-validation](tasks/11-pipeline-validation.md))
* [x] Refactor hook execution to use Registry hooks (HookName), remove old dispatcher/protocol if redundant. (Task: [12-pipeline-hooks](tasks/12-pipeline-hooks.md))

### D) Output writer changes (new default ordering)

* [x] Implement output ordering rule:

  * [x] mapped columns in **input column order** (Task: [13-output-ordering-mapped-input-order](tasks/13-output-ordering-mapped-input-order.md))
  * [x] unmapped columns appended right (if enabled) (Task: [14-output-ordering-unmapped-append](tasks/14-output-ordering-unmapped-append.md))
* [x] Add a supported “manual reorder” path via hook (recommended: `HookName.ON_TABLE_MAPPED`). (Task: [15-output-manual-reorder-hook](tasks/15-output-manual-reorder-hook.md))

### E) Settings refactor

* [x] Implement `ade_engine.settings.Settings` via `pydantic_settings` with:

  * [x] defaults < TOML < `.env` < env vars < init kwargs (Task: [16-settings-implementation](tasks/16-settings-implementation.md))
  * [x] keys: `append_unmapped_columns`, `unmapped_prefix`, `mapping_tie_resolution` (leftmost|drop_all), etc.
* [x] Update engine + pipeline to read Settings (not manifest/config writer blocks). (Task: [17-settings-pipeline-integration](tasks/17-settings-pipeline-integration.md))

### F) Remove legacy code + docs

* [x] Delete `ade_engine/config/*` legacy manifest/loader modules. (Task: [18-remove-legacy-config](tasks/18-remove-legacy-config.md))
* [x] Delete `ade_engine/schemas/manifest.py` (and any manifest schema plumbing). (Task: [19-remove-manifest-schema](tasks/19-remove-manifest-schema.md))
* [x] Remove/replace old docs referring to TOML manifest columns ordering & module strings. (Task: [20-docs-cleanup-manifest-refs](tasks/20-docs-cleanup-manifest-refs.md))
* [x] Update README(s) to the new “registry config package” model. (Task: [21-update-readmes-registry-model.md))

### G) Config package template (ade-config, ADE Engine)

* [x] Remove `manifest.toml` requirement. (Task: [22-config-package-no-manifest](tasks/22-config-package-no-manifest.md))
* [x] Provide recommended folder layout + examples (but keep registry flexible). (Task: [23-config-package-layout-examples](tasks/23-config-package-layout-examples.md))
* [x] Update config package README/docs to new approach. (Task: [24-config-package-docs-update](tasks/24-config-package-docs-update.md))

### H) Tests

* [x] Unit tests: registry ordering + score patch normalization. (Task: [25-tests-registry-ordering-scorepatch](tasks/25-tests-registry-ordering-scorepatch.md))
* [x] Unit tests: discovery imports all modules deterministically. (Task: [26-tests-discovery](tasks/26-tests-discovery.md))
* [x] Integration test: small sample config package → run pipeline end-to-end. (Task: [27-tests-integration-e2e](tasks/27-tests-integration-e2e.md))

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Implement Settings precedence — abc1234`

---

# ADE Engine refactor: Registry config packages + Settings-driven engine

## 1. Objective

**Goal:**
Replace the current TOML/manifest + module-string loader architecture with a **registry-based, code-first config package** that is:

* dead simple to understand,
* dynamically discoverable (drop in Python files → it works),
* uses standard naming and structure,
* removes legacy/duplicate plumbing,
* does **not** require explicit column ordering,
* centralizes engine toggles in standard **pydantic-settings** config (`.env` / env vars / optional TOML).

**You will:**

* Introduce a **Registry** as the single interface between ade-engine and ade-config.
* Load ade-config by importing modules (decorators register items).
* Rewire pipeline stages to read from registry.
* Remove legacy manifest parsing, schema, and config loaders.
* Move writer behavior into `ade_engine.settings.Settings`.

**Result should:**

* Run ADE with a config package that contains only Python files (no `manifest.toml`).
* Execute Row Detectors / Column Detectors / Column Transforms / Column Validators / Hooks from registry.
* Output mapped columns in input order; append unmapped columns at end (if enabled).
* Allow optional manual output reordering via hook.
* Use `.env`/env/TOML for engine settings with safe defaults.

---

## 2. Context (What you are starting from)

### Current ade-engine

* `ade_engine/config/*` loads a TOML manifest and points to module strings for detectors and hooks.
* Pipeline stages rely on that manifest-derived structure.
* Hooks are dispatched via a custom dispatcher/protocol layer.
* Writer behavior (`append_unmapped_columns`, `unmapped_prefix`) lives in the manifest.

### Current ade-config

* `manifest.toml` lists columns in a fixed order, with module strings.
* Detectors live in `column_detectors/` and `row_detectors/`.
* Hooks live in `hooks/` with one file per hook.

This is workable but creates:

* lots of switches and wiring,
* duplicated “what exists” metadata in TOML + filesystem,
* brittle ordering configuration,
* unnecessary loader complexity.

---

## 3. Target architecture / structure (ideal)

The config package is “just a Python package” that registers itself on import.

### Target file tree (ade-engine)

```text
apps/ade-engine/src/ade_engine/
  __init__.py
  __main__.py
  main.py
  engine.py
  settings.py                 # pydantic-settings (.env/env/TOML), engine-wide toggles
  registry/
    __init__.py
    models.py                 # FieldDef, detector defs, hook defs, contexts, return types
    decorators.py             # @row_detector, @column_detector, @column_transform, @column_validator, @hook
    registry.py               # Registry class + ordering rules
    discovery.py              # import_all(package) for auto-discovery
  pipeline/
    pipeline.py               # orchestrates stages, calls hooks
    extract.py
    detect_rows.py            # uses registry.row_detectors
    detect_columns.py         # uses registry.column_detectors + registry.fields
    mapping.py
    transform.py              # uses registry.column_transforms
    validate.py               # uses registry.column_validators
    render.py                 # output ordering: mapped-in-input-order + unmapped appended
  types/
    ...                       # keep only what is still needed; prune aggressively
```

### Target file tree (ade-config recommended layout for ADE Engine)

> Flexible by design: devs can put files anywhere under the package.
> This layout is just the recommended “standard, intuitive” convention.

```text
ade_config/
  __init__.py                 # imports subpackages (or relies on engine discovery)
  meta.py                     # name/description/api_version (optional but recommended)

  columns/
    email.py                  # field + detectors + transform + validator (all in one place)
    first_name.py
    ...
  rows/
    header.py                 # row detectors
    data.py
  hooks/
    on_table_mapped.py        # advanced tweaks (e.g. reorder output columns)
    on_workbook_before_save.py
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Zero manifest**: no TOML required for wiring.
* **Dynamic**: add a `.py` file → it registers automatically.
* **Standard**: decorators + dataclasses + enums; minimal magic.
* **Deterministic**: stable ordering (priority then import path).
* **Simplified output**: no manual column order; preserve input order.
* **Centralized settings**: engine toggles in `.env`/env/TOML, safe defaults.

### 4.2 Key components / modules

**Registry**

* Stores:

  * Field definitions (`FieldDef`)
  * Row Detectors
  * Column Detectors
  * Column Transforms
  * Column Validators
  * Hooks keyed by `HookName`
* Defines ordering rules and normalization helpers (e.g. “ScorePatch”).

**Discovery**

* Imports config package modules recursively to trigger decorator registration.
* One code path; no “module string list” or manifest parsing.

**Pipeline integration**

* Each stage asks the registry: “what should I run now?”
* Hooks run via registry at defined hook points.

**Settings**

* `ade_engine.settings.Settings` controls engine-level behavior:

  * `append_unmapped_columns`
  * `unmapped_prefix`
  * (and any other engine toggles)
* Loaded via `.env` / env vars / optional TOML.

### 4.3 Key flows / pipelines (high level)

1. **Load Settings**
2. **Load Config Package → Registry** (import modules, registry fills)
3. **Extract workbook**
4. **Row detection** → find header row(s) / table boundary
5. **Column detection** → score fields per column
6. **Mapping** → pick best field per column
7. **Hook: ON_TABLE_MAPPED** (optional: reorder output, patch mapping, call LLM, etc.)
8. **Transform** mapped columns
9. **Validate** mapped columns (report only)
10. **Render output workbook** with ordering rule
11. **Hook: ON_WORKBOOK_BEFORE_SAVE** (final adjustments)
12. Save

### 4.4 Open questions / decisions (resolve during implementation)

* **Row labels**: finalize canonical row classes (e.g. `header`, `data`, `unknown`).
* **Validation return type**: keep `bool` for simplicity vs return rich issues list.
* **Hook mutation model**: in-place mutation vs “return patched object” (recommend in-place for simplicity + explicitness).
* **Duplicate mapping policy**: if two input columns map to same field, decide “first wins” vs “highest score wins” and how to treat the loser (unmapped).

---

## 5. Implementation & notes for agents

* **No backwards compatibility**: delete legacy modules rather than keeping adapters.
* Prefer **small commits**: introduce registry + tests first, then discovery, then pipeline stage rewires, then delete legacy.
* Keep the “recommended config layout” minimal but documented.
* The GUI web editor should only need:

  * creating Python files,
  * optionally editing `.env` or `ade_engine.toml` for engine settings.
* Output ordering rule is now:

  * mapped columns ordered by the input column index,
  * unmapped appended to the right with `unmapped_prefix` (if enabled),
  * any “business-specific reorder” happens in a hook (recommended: `ON_TABLE_MAPPED`).

---

# Supporting documents (rough drafts + what goes in each)

Below are the supporting docs I’d create alongside the work package. Each is intentionally “copy/paste-able” into `apps/ade-engine/docs/ade-engine/…` (and the config package docs as needed).

---

## Doc 1 — `docs/ade-engine/architecture.md`

**Title:** ADE Engine Architecture (Registry + Settings)

**Contents draft:**

* **Why this change**

  * pain points in manifest wiring
  * goals: dynamic, standard, fewer switches
* **Big picture**

  * “Config package registers capabilities; engine runs pipeline using registry.”
* **Major components**

  * Settings (pydantic-settings)
  * Registry (definitions + ordering)
  * Discovery (import-all)
  * Pipeline stages + hook points
* **Non-goals**

  * backwards compatibility
  * supporting untrusted code packages

---

## Doc 2 — `docs/ade-engine/registry-spec.md`

**Title:** Registry Spec (Fields, Detectors, Transforms, Validators, Hooks)

**Contents draft:**

* **Core types**

  * `FieldDef(name, label, synonyms, required, dtype, ...)`
  * `DetectorDef(kind, fn, priority, applies_to, ...)`
  * `HookDef(hook_name, fn, priority, ...)`
* **Ordering rules (deterministic)**

  * sort by `(priority desc, module_path asc, qualname asc)`
* **Normalization**

  * `ScorePatch = float | dict[str, float]`
  * `normalize_score_patch(current_field, patch)` → dict always
* **Registration**

  * decorators:

    * `@field(...)`
    * `@row_detector(...)`
    * `@column_detector(...)`
    * `@column_transform(...)`
    * `@column_validator(...)`
    * `@hook(HookName...)`
* **Validation rules**

  * detector patches referencing unknown fields → ignored (or warn)
  * duplicate field registrations → error (fail fast)

---

## Doc 3 — `docs/ade-engine/callable-contracts.md`

**Title:** Callable contracts (signatures, contexts, return types)

**Contents draft:**

* **Design principle:** “callables are the simplest plugin API”
* **Contexts**

  * `RowDetectorContext`: workbook, sheet, row index, row values sample, state, logger, run metadata
  * `ColumnDetectorContext`: column index, header, column values, samples, state, logger
  * `TransformContext`: field name, column values, mapping, state
  * `ValidateContext`: field name, column values, state
  * `HookContext` variants per HookName
* **Return types**

  * Row/Column detectors: `ScorePatch`
  * Transform: returns transformed values (or mutates list)
  * Validate: `bool` (simple) OR list of issues (optional future)
  * Hooks: `None` (mutate context objects) for simplicity
* **Examples**

  * detector that boosts one field and penalizes others
  * transform that normalizes phone numbers
  * validator that checks emails

---

## Doc 4 — `docs/ade-engine/pipeline-and-registry.md`

**Title:** How the pipeline uses the registry (simple explanation)

**Contents draft:**

* **Step-by-step flow** mapping each pipeline phase to registry calls:

  * load registry
  * run row detectors over rows → choose header row
  * run column detectors over columns → score fields
  * mapping selection
  * hook `ON_TABLE_MAPPED`
  * transforms + validators
  * render + hooks
* **Where “state” lives**

  * per-run mutable dict
  * passed to all callables
* **Tie-breakers**

  * score ties resolved deterministically
* **Failure behavior**

  * detector exceptions → record issue and continue (or fail fast; decide)
  * hook exceptions → default fail fast (recommended)

---

## Doc 5 — `docs/ade-engine/hooks.md`

**Title:** Hooks (HookName, when they run, what they can change)

**Contents draft:**

* **HookName enum**

  * `ON_WORKBOOK_START`
  * `ON_SHEET_START`
  * `ON_TABLE_DETECTED`
  * `ON_TABLE_MAPPED`
  * `ON_TABLE_WRITTEN`
  * `ON_WORKBOOK_BEFORE_SAVE`
* **Hook contexts**

  * what objects are provided at each stage
* **Recommended pattern:** mutate in place
* **Column reordering (now optional, advanced)**

  * default behavior: mapped-in-input-order + unmapped appended
  * reordering belongs in `ON_TABLE_MAPPED`
  * show a helper API like `table.reorder_columns(...)`
* **Examples**

  * using LLM to patch mapping during `ON_TABLE_MAPPED`
  * formatting the output workbook before save

---

## Doc 6 — `docs/ade-engine/output-ordering.md`

**Title:** Output column ordering rules (ADE Engine)

**Contents draft:**

* **Default rule**

  * preserve input order for mapped columns
  * unmapped appended right if enabled
* **Settings**

  * `append_unmapped_columns`
  * `unmapped_prefix`
* **Examples**

  * input columns vs output columns (simple diagram)
* **How to reorder**

  * “if you care, do it in a hook”
  * recommended hook + snippet

---

## Doc 7 — `docs/ade-engine/settings.md`

**Title:** Engine settings (.env / env vars / TOML)

**Contents draft:**

* **Why settings moved out of config manifest**
* **Precedence**

  * defaults < TOML < `.env` < env vars < init kwargs
* **Supported keys**

  * `ADE_ENGINE_APPEND_UNMAPPED_COLUMNS`
  * `ADE_ENGINE_UNMAPPED_PREFIX`
  * `ADE_ENGINE_CONFIG_PACKAGE`
  * `ADE_ENGINE_CONFIG_ROOT`
  * `ADE_ENGINE_LOG_LEVEL`, etc.
* **Examples**

  * `.env`
  * `ade_engine.toml`
* **Safe defaults**

  * what happens when nothing is present

---

## Doc 8 — `docs/ade-engine/config-package-conventions.md`

**Title:** ade-config (ADE Engine): recommended conventions

**Contents draft:**

* **What a config package is**

  * “a normal Python package that registers things when imported”
* **Recommended folder layout**

  * `columns/`, `rows/`, `hooks/`
* **One file per column**

  * field definition + detectors + transform + validator in one place
* **Naming conventions**

  * keep function names descriptive; registry doesn’t require it but humans do
* **Minimal example**

  * `columns/email.py`
  * `rows/header.py`
  * `hooks/on_table_mapped.py`
* **How GUI users add new logic**

  * create file → import decorators → write function → done

---

## Doc 9 — `docs/ade-engine/legacy-removals.md`

**Title:** What we deleted and why

**Contents draft:**

* **Engine deletions**

  * `ade_engine/config/*` (manifest loader, module-string wiring)
  * `ade_engine/schemas/manifest.py`
  * possibly `hooks/dispatcher.py` / `protocol.py` if replaced by registry hook runner
* **Config package deletions**

  * `manifest.toml`
  * “columns list” + ordering concerns
* **Resulting simplifications**

  * fewer moving parts, fewer sources of truth

---

## Doc 10 — `docs/ade-engine/testing-plan.md`

**Title:** Testing plan for ADE Engine

**Contents draft:**

* Unit tests:

  * registry ordering
  * score patch normalization
  * discovery imports
* Integration tests:

  * tiny config package fixture
  * 1 workbook fixture (header row + a few columns)
  * asserts mapping + output ordering + hook invocation

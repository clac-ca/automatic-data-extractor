# ADE Engine Architecture (Registry + Settings)

**Status:** Draft (aligned to workpackage, Dec 10 2025)  
**Scope:** ADE Engine refactor (registry-based config packages, no manifest)

---

## 1. Purpose

Describe the target architecture for the refactored **ADE Engine** that normalizes Excel/CSV files using:
- a **registry** of fields/detectors/transforms/validators/hooks,
- **dynamic discovery** (import modules, decorators register),
- **settings** for engine behavior (pydantic-settings),
- simplified **output ordering** (input order for mapped columns; optional unmapped appended).

---

## 2. Why this change

**Old model:** TOML manifest listed columns, module strings, explicit output order; loader and dispatcher layers added complexity.  
**New model:** Config is just Python code. Importing it registers capabilities; the pipeline asks the registry what exists. Output ordering is handled by the engine (input order), with hooks for advanced reordering.

Goals: dynamic & obvious, fewer sources of truth, deterministic execution, and standard settings handling.

---

## 3. Big picture

```
Config package (.py files) --imports--> Registry (in-memory catalog)
Registry --drives--> Pipeline stages (detect/map/transform/validate/render)
Settings (.env/env/TOML) --configure--> Engine behavior (writer toggles, config package path)
Hooks --patch/extend--> mapping, ordering, workbook tweaks
```

---

## 4. Major components

- **Settings (`ade_engine.settings.Settings`)**
  - Loaded via pydantic-settings; precedence: init kwargs > env vars > `.env` > `ade_engine.toml` > defaults.
  - Keys: `config_package="ade_config"`, `append_unmapped_columns=True`, `unmapped_prefix="raw_"` (and future toggles).

- **Registry (`ade_engine/registry/*`)**
  - Models: `FieldDef`, `RegisteredFn`, contexts, `HookName`.
  - Decorators: `field_meta` (optional metadata helper), `row_detector`, `column_detector`, `column_transform`, `column_validator`, `hook`.
  - Deterministic ordering: sort by priority desc, module path asc, qualname asc.

- **Discovery (`registry/discovery.py`)**
  - `import_all(package_name)` walks and imports modules under the config package; registration happens at import time.
  - Registry is finalized (sorted) after discovery.

- **Pipeline (`pipeline/*`)**
  - Steps: extract → detect rows → detect columns → mapping → `ON_TABLE_MAPPED` hook → transform → validate → render → `ON_WORKBOOK_BEFORE_SAVE`.
  - Each stage pulls callables from the registry.

- **Hooks**
  - `HookName` values include `ON_WORKBOOK_START`, `ON_SHEET_START`, `ON_TABLE_DETECTED`, `ON_TABLE_MAPPED`, `ON_TABLE_WRITTEN`, `ON_WORKBOOK_BEFORE_SAVE`.
  - Hooks mutate provided context objects; ordering follows registry sort rules.

---

## 5. Pipeline flow (concise)

1) **Load settings**  
2) **Build registry**: create registry → set as current → import config package modules → finalize (sort)  
3) **Extract** workbook/sheets  
4) **Row detection**: run `row_detectors` per row to score kinds; pick header row/table bounds  
5) **Column detection**: run `column_detectors` per column → score patches → accumulate per field  
6) **Mapping**: choose best field per column (highest-score-wins); enforce one-to-one mapping. Score ties are resolved by `settings.mapping_tie_resolution` (`leftmost` default, or `drop_all` to leave all tied columns unmapped).  
7) **Hook `ON_TABLE_MAPPED`**: patch mapping, reorder, add derived columns, etc.  
8) **Transform** mapped columns (`column_transforms`)  
9) **Validate** mapped columns (`column_validators`, reporting-only)  
10) **Render** output: mapped columns in **input order**; append unmapped right if `append_unmapped_columns` (header prefix `unmapped_prefix`).  
11) **Hook `ON_WORKBOOK_BEFORE_SAVE`**: final formatting/tweaks → save.

Determinism: registry ordering + deterministic tie-breaks ensure stable results.

---

## 6. Output ordering (engine-owned)

- Default: mapped columns keep input order.  
- Unmapped columns appended to the right when enabled; headers prefixed with `unmapped_prefix`.  
- Custom orders belong in a hook (recommended: `ON_TABLE_MAPPED`, reorder `table.columns`).

---

## 7. Config package shape (recommended)

```
ade_config/
  __init__.py
  columns/*.py   # field + detectors + transform + validator
  rows/*.py      # row detectors
  hooks/*.py     # hook implementations (e.g., on_table_mapped.py)
  common/*.py    # shared helpers (optional)
```

No `manifest.toml` required; adding a Python file + decorator registrations is enough.

---

## 8. Settings details

- Env prefix: `ADE_ENGINE_`  
- Files: `.env` (optional), `ade_engine.toml` with `[ade_engine]` section.  
- Precedence: init kwargs > env vars > `.env` > TOML > defaults.  
- Keep settings out of config packages; they are engine concerns.

---

## 9. Observability & errors

- Log: which config package was loaded, counts of registered items, detector/validator summaries, mapping decisions, hook executions.  
- Error policy: detector exceptions recorded and continue; hook exceptions default to fail-fast (config bug); duplicate field registration is an error.

---

## 10. Non-goals

- No backwards compatibility with manifest-based loader.  
- No explicit column order in config.  
- No module-string wiring lists in config.  
- Not a general workflow/orchestration platform—scope is Excel/CSV normalization via registry plugins.

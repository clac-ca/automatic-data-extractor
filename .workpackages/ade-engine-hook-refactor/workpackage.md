> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

- [x] Document current hook `table` object lifecycle (`TableData`)
- [x] Confirm `on_table_mapped` runs after mapping (and what “after mapping” means today)
- [x] Decide on new extension-facing hook table contract (API + invariants)
- [x] Define mapping-hook return/patch contract (no in-place mutation)
- [ ] Implement adapter + pipeline changes (engine internal stays `TableData`)
- [ ] Update docs + template config package + add focused tests

---

# ADE Engine hook table refactor (make hook `table` intuitive)

## 1. Objective

Make the `table` object passed into ADE Engine hooks:

- Intuitive to **inspect** (consistent fields across hook stages)
- Safe and ergonomic to **modify** (explicit, validated “patch” semantics instead of mutating internal lists)
- Clear about what can be **returned** to the engine (hook return contracts, where applicable)

Non-goals:

- Replace transforms/validators (value changes should remain transform/validator territory)
- Change the engine’s internal storage model (`TableData`) unless needed for the external contract

## 2. Context (what we are starting from)

Today all hooks receive `table: TableData | None` (via `HookContext.table`). `TableData` is an engine-internal dataclass that accumulates more fields as the pipeline progresses.

### 2.1 Current hook timing + what `table` contains

Hook stage order (engine docs + code):

- `on_table_detected`
  - Runs after column mapping (`detect_and_map_columns`), before transforms/validators.
  - `TableData` populated with:
    - `source_columns` (raw header + raw values per source column)
    - `mapped_columns` (field_name + source_index + raw values)
    - `unmapped_columns`
    - `column_scores`, `duplicate_unmapped_indices`, `region`, etc.
  - Not yet set (currently): `row_count`, `columns` (canonical store), `mapping` (canonical map), `issues*`, `output_*`

- `on_table_mapped`
  - Runs immediately after `on_table_detected`.
  - Docs say: “Mutating `table.mapped_columns` / `table.unmapped_columns` is allowed.”
  - Pipeline then computes:
    - `table.row_count`
    - `table.columns = {field_name: values_vec}`
    - `table.mapping = {field_name: source_index}`
  - Transforms/validators run next, mutating `table.columns` + producing `issues`.

- `on_table_written`
  - Runs after transforms/validators and after render to the output worksheet.
  - `table.columns`, `table.mapping`, `table.issues_patch`, `table.issues`, `table.output_range`, `table.output_sheet_name` are populated.
  - `sheet` in the hook context is the **output** worksheet.

### 2.2 Pain points with the current `TableData` contract (hooks)

- **Stage-dependent shape**: many properties exist only “later”, but the type looks the same across hooks.
- **Implicit mutation contract**: mapping edits require mutating `table.mapped_columns` / `table.unmapped_columns` lists directly.
- **Overwrites surprise**: even if a hook sets `table.columns` / `table.mapping` during `on_table_mapped`, the pipeline overwrites them right after the hook.
- **Return values are not meaningful** for hooks today (docs say hooks return `None`), so “patching” must be in-place.
- **Engine-internal leakage**: exposing `TableData` makes it harder to evolve engine internals without breaking config packages.

### 2.3 Confirmation: is `on_table_mapped` “after mapping” with new headers?

Yes, **mapping has already occurred** when `on_table_mapped` runs: `detect_and_map_columns(...)` has produced `MappedColumn(field_name=...)` entries and the hook sees those.

However, **the canonical column store does not exist yet** at this hook today:

- At `on_table_mapped`, `table.columns` is still empty (it’s built *after* the hook returns).
- “New headers” exist only as `MappedColumn.field_name` values (canonical field names), not as a rewritten header row or a populated `table.columns` dict.

## 3. Target architecture / structure (ideal)

### 3.1 Core idea

Keep `TableData` as the internal pipeline model, but stop exposing it directly as the primary hook contract.

Instead, pass a stable, extension-facing `HookTable` object into hooks:

- Read-only by default (so hooks can’t accidentally corrupt invariants)
- Provides ergonomic helpers for common inspection tasks
- Allows **explicit** mutations via validated patch objects (especially for mapping)

### 3.2 Proposed file-level changes (expected)

```text
apps/ade-engine/src/ade_engine/models/extension_contexts.py      # HookContext gets a better-typed `table`
apps/ade-engine/src/ade_engine/models/hook_table.py             # NEW: HookTable + views + patch types
apps/ade-engine/src/ade_engine/application/pipeline/pipeline.py # Apply mapping patches between hooks and transforms
apps/ade-engine/src/ade_engine/extensions/registry.py           # Allow hook return values when enabled per hook
apps/ade-engine/docs/hooks.md                                   # Update hook table contract + examples
apps/ade-engine/docs/callable-contracts.md                      # Document mapping-hook return type + validation
apps/ade-engine/src/ade_engine/extensions/templates/.../hooks/  # Update templates
```

## 4. Design (for this workpackage)

### 4.1 Design goals

- **Clarity:** hook authors can tell what’s available at each stage without guessing.
- **Ergonomics:** common tasks should be 1–3 obvious calls (not list surgery).
- **Safety:** no silent invariant breakage; mapping edits must be validated.
- **Stability:** engine internals can change while hook contract remains stable.
- **Determinism:** multiple hooks compose predictably (priority order, sequential patch application).

### 4.2 Proposed hook `table` API (extension-facing)

Introduce `HookTable` (passed as `table`), with a small set of consistently-present views:

- `table.identity`
  - `sheet_name`, `sheet_index`, `table_index`
  - `region` (header/data bounds, inferred header flag)

- `table.source`
  - `columns`: index-addressable source columns (`index`, `header`, `values`, `values_sample`)
  - helper lookups: `header_strings()`, `column(index)`, `sample_rows(n)`

- `table.mapping` (available starting `on_table_detected`)
  - `mapped`: ordered mapping entries (`field_name`, `source_index`, `source_header`, `score`)
  - `unmapped`: source columns not mapped
  - helper: `mapped_fields()`, `lookup(field_name)`, `reverse_lookup(source_index)`

- `table.canonical` (available starting `on_table_detected`, but read-only)
  - `columns: Mapping[str, list[Any]]` keyed by canonical `field_name`
  - `row_count`
  - NOTE: built from `mapping.mapped` (so hook authors always have “post-mapping” column vectors)

- `table.results` (populated after transforms/validators/render)
  - `issues_patch`, `issues` (flattened), `output_sheet_name`, `output_range`

Key constraint: `HookTable` is *not* a dataframe; it’s a thin, stable facade over ADE’s column-vector model.

### 4.3 Mapping edits: return a patch (no in-place mutation)

Change only one hook to accept meaningful return values:

- `on_table_mapped` may return a `TableMappingPatch` (or `None`).
- The engine applies patches **sequentially** in hook execution order (priority desc, then module/qualname).
- Any invalid patch raises `HookError` with stage `on_table_mapped`.

#### 4.3.1 Patch shape (Python-friendly, no imports required)

Allow either a dataclass instance or a plain dict with these keys:

```py
{
  "map": {"field_name": 3, ...},          # set/overwrite field->source_index
  "unmap": ["field_name", ...],           # remove field mapping
  "order": ["field_name", ...],           # optional mapped-field output order
  "drop_passthrough": [7, 8, ...],        # optional: drop specific source columns from passthrough/unmapped output
  "rename_passthrough": {7: "raw_notes"}  # optional: override passthrough header
}
```

Validation rules:

- `field_name` must be a registered field.
- `source_index` must exist in `table.source.columns`.
- No two fields may map to the same `source_index` after patch application.
- `order`, if present, must contain exactly the mapped fields (or define a clear rule: “subset allowed + append remainder” — decide).

### 4.4 Compatibility / migration plan

We likely have existing configs that touch `TableData` directly.

Preferred approach:

- `HookTable` wraps `TableData` and **proxies** legacy attributes (`mapped_columns`, `unmapped_columns`, etc.) for a transition window.
- Docs + templates move to the new API immediately.
- Add a warning path (logger debug/event) when legacy mutation is detected in `on_table_mapped`.
- After one or two releases, freeze/remove legacy mutation.

### 4.5 Open questions / decisions to resolve

Decisions for v1:

- `order` is **partial**: if provided, it must be a list of unique mapped field names; the engine orders those first and appends remaining mapped fields in their existing order.
- Patch mapping is **by source index** (unambiguous). `HookTable` should provide helpers to find candidate indices from header text/samples.
- Passthrough/unmapped rename/drop is handled **before render** via the mapping patch (preferred over post-write worksheet surgery).
- Output headers remain **`field_name`** (no `FieldDef.label` rendering changes in this refactor).

## 5. Implementation notes (when we start coding)

- Build `HookTable` from internal `TableData` at hook invocation time.
  - For `on_table_detected` / `on_table_mapped`, `HookTable.canonical` should be available by building a temporary column store from `mapped_columns` + `row_count`.
  - For `on_table_written`, `HookTable.results` can reference `TableData.columns/issues/output_*`.
- Apply mapping patches in `Pipeline._process_table`:
  - Construct `HookTable` → run hooks one at a time → apply patch → rebuild mapping view → continue.
- Add tests that:
  - Confirm `on_table_mapped` sees canonical field names + canonical vectors.
  - Confirm sequential patch application and validation.
  - Confirm backward-compat attribute access for a transition window (if we choose proxying).

> **Agent instruction (read first):**
>
> * Treat this work package as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * If you must change the plan, **update this document first**, then the code.

---

# Work Package: ADE Engine — Single-Table DataFrame Pipeline (Simplify + De-internalize)

## What we’re doing (plain terms)

ADE should feel like: **“I’m just working with a normal table.”**

Today, the engine constructs and threads stage-specific internal table objects (`TableData` / `TableView`) through mapping, transforms, validation, and rendering. That creates:

* stage-dependent shapes,
* unclear mutability,
* extension contracts that leak engine internals,
* and a bunch of glue code (column stores, unmapped passthrough stitching, prefixes, etc.).

### New core principle

> ADE works on **one** `polars.DataFrame` called `table`.
> Mapping **renames headers**. Everything else just operates on the DataFrame.

This work package intentionally **breaks** legacy extension contracts. No adapters.

---

## Summary of the simplification

### The “single table” model

* As soon as ADE extracts a detected table region, it materializes **one** `table: pl.DataFrame`.
* Initially, `table` is the raw extracted table:

  * columns = extracted header values (minimally normalized to safe, unique strings)
  * rows = extracted data rows
* That **same** DataFrame is the only table object for the rest of the pipeline.

### Mapping is just a rename

* Mapping does not build a “canonical table” or “mapped/unmapped stores”.
* Mapping produces a rename plan and applies it:

  * extracted header name → canonical field name
* Anything not mapped simply stays as a normal column with its extracted name.

### “Unmapped columns” aren’t special anymore

* We remove the idea of “append passthrough columns”.
* Default behavior: **write whatever columns are currently in `table`.**
* If a user wants to drop non-canonical columns, we provide one setting:

  * `remove_unmapped_columns: bool = false` (default)

---

## Work Package Checklist

* [x] Align on “one DataFrame” as the only table artifact
* [x] Align on “mapping = rename headers” (no canonical/unmapped dual tables)
* [ ] Introduce DF-native contexts for hooks/transforms/validators
* [ ] Remove legacy `TableData`/`TableView` surfaces (code + docs + templates)
* [ ] Remove `on_table_detected` everywhere
* [ ] Implement extraction → `table: pl.DataFrame` materialization as the stage boundary
* [ ] Implement mapping-as-rename with deterministic collision handling
* [ ] Keep table hook stages and return-DF semantics:

  * `on_table_mapped` → `on_table_transformed` → `on_table_validated` → `on_table_written`
* [ ] Replace `append_unmapped_columns` with `remove_unmapped_columns` (default `false`)
* [ ] Refactor transforms to a Polars-native contract (breaking)
* [ ] Refactor validators to a Polars-native contract (breaking)
* [ ] Render/write directly from the final `table` DataFrame
* [ ] Update docs + template config package + focused tests

---

# 1) Design goals

## 1.1 Goals

1. **Reduce engine complexity** by removing internal intermediate table representations.
2. **Make extension contracts stable**: hooks/transforms/validators receive `pl.DataFrame`.
3. **Make mutability explicit**: change the table by returning a new DataFrame.
4. **Make output obvious**: the DataFrame written is the DataFrame you see.

## 1.2 Non-goals

* Backwards compatibility for legacy config packages.
* “Dual table” designs (no `original_unmapped_table`, no join-based passthrough stitching).
* Complex output ordering rules baked into the engine (column order is whatever the DataFrame is at write time).
* Making the source workbook mutable (input is read-only; output is mutable post-write).

---

# 2) Table model (one DataFrame)

## 2.1 Materialization boundary

As soon as a table region is extracted (header row + data rows), the engine builds:

* `table: pl.DataFrame`

No other table-shaped artifact exists.

Engine internals can keep metadata (region, mapping scores, etc.) but **values live in `table`**.

## 2.2 Minimal header normalization (safe + deterministic)

Polars requires unique string column names, but Excel headers can be empty/duplicated/non-strings.

Column name assignment (in source column order):

1. `base = str(header).strip()` if non-empty else `f"col_{i+1}"`
2. Deduplicate collisions by suffixing: `"<base>__2"`, `"<base>__3"`, …

That’s it. No lowercasing/tokenization. We preserve “raw-ness” while keeping the DataFrame valid.

---

# 3) Mapping (rename-only)

## 3.1 Mapping behavior

Mapping applies as a rename on the existing DataFrame:

* For each mapped column: rename extracted name → canonical field name.
* Unmapped columns remain unchanged and remain in the DataFrame.

There is no “canonical vs passthrough” construction phase anymore.

## 3.2 Collision handling (deterministic)

Mapping must not produce duplicate column names.

Rule:

* If renaming a column to a canonical field name would collide with an existing column name, the rename is **skipped** and the column remains unmapped (keeps its extracted name).

This avoids inventing suffixed canonical names (which would be surprising and hard to validate against).

The engine must log a clear warning indicating:

* the extracted column
* the intended canonical name
* the existing conflicting column
* that the rename was skipped

---

# 4) Output behavior: `remove_unmapped_columns`

We replace the old “append passthrough columns” feature with a simpler model:

* The output is whatever columns are in `table` at write time.

Add one setting:

* `remove_unmapped_columns: bool = false` (default)

Behavior:

* `false` (default): write all columns in `table`
* `true`: right before write, drop columns whose names are **not registered canonical fields**

  * (engine-reserved columns, if any exist, follow the same rule unless explicitly reserved—see note below)

This eliminates:

* `append_unmapped_columns`
* `unmapped_prefix`
* passthrough stitching logic
* and the conceptual split between “data” and “raw passthrough data”

---

# 5) Hook stages and mutation rules (simple + enforceable)

## 5.1 Table lifecycle

One table flows through:

**extract → mapping(rename) → hooks → transforms → hooks → validation → hooks → write → hooks**

Specifically:

1. `table` is extracted (raw headers)
2. mapping renames columns in-place (producing a new DF instance, since Polars)
3. `on_table_mapped`
4. transforms
5. `on_table_transformed`
6. validation
7. `on_table_validated`
8. write
9. `on_table_written`

We remove `on_table_detected` (redundant; detection is not a stable “table” state anymore).

## 5.2 Hook semantics (stage contracts)

### `on_table_mapped` (post-mapping, pre-transform)

* Input: `table: pl.DataFrame`
* Return: `None` or new `pl.DataFrame`
* Allowed:

  * rename/select/with_columns
  * filter/sort (row ops allowed)
  * reorder columns

### `on_table_transformed` (post-transform, pre-validation)

* Input: `table: pl.DataFrame`
* Return: `None` or new `pl.DataFrame`
* Allowed:

  * rename/select/with_columns
  * filter/sort (row ops allowed)
  * reorder columns

### `on_table_validated` (post-validation, pre-write)

* Input: `table: pl.DataFrame` + validation results
* Return: `None` or new `pl.DataFrame`
* Allowed:

  * **column shaping only** (rename/select/reorder/add computed columns)
* Not allowed:

  * changing row count or row order

Rationale: validator outputs are keyed to row indices at the time of validation.

### `on_table_written` (post-write)

* Input: `table` (the written table), plus output sheet/workbook and validation results
* Return: `None`
* Allowed:

  * formatting, summaries, additional sheets, charts
* Not allowed:

  * changing the data table (it’s already committed)

## 5.3 Hook return composition

Hooks run in priority order.

* If a hook returns a DataFrame, that becomes the input to the next hook at the same stage.
* If it returns `None`, the table is unchanged.

This enables “small composable hooks” without any in-place mutation.

---

# 6) New extension contracts (breaking, simplified)

## 6.1 Hook registration (unchanged mechanism, new inputs)

Hooks are registered as before, but now the stable table input is always:

* `table: pl.DataFrame`

Table hook context fields (keyword-only; authors may accept what they want):

* Identity: `sheet_name`, `sheet_index`, `table_index`, `region`
* Table: `table: pl.DataFrame`
* Diagnostics: `mapping` (rename plan + confidences), `column_scores` (optional)
* Validation (validated+): `issues_patch`, `issues`
* Standard: `metadata`, `state`, `input_file_name`, `logger`
* Workbook objects:

  * pre-write hooks receive source workbook/sheet (read-only by convention)
  * post-write hook receives output workbook/sheet (mutable)

## 6.2 Transforms (v3, Polars-native)

Transforms remain “registered per field” but operate on the DataFrame.

**Signature (recommended):**

```py
def transform(*, field_name: str, table: pl.DataFrame, state: dict, metadata: dict, logger, **_) -> pl.Expr | dict[str, pl.Expr] | None:
    ...
```

Return types (kept intentionally small to reduce engine normalization complexity):

* `None` → no change
* `pl.Expr` → replacement expression for `field_name`
* `dict[str, pl.Expr]` → multi-output derived fields

Constraints:

* Transforms MUST NOT change row count.
* Derived output fields MUST be registered canonical fields.

Engine behavior:

* Apply results via `with_columns`.
* Transform execution order is **registry order** of fields present in the table (simplest, predictable).

## 6.3 Validators (v3, simplified return shape)

Validators operate on the DataFrame and return a simple list of row-indexed issues.

**Signature (recommended):**

```py
def validate(*, field_name: str, table: pl.DataFrame, state: dict, metadata: dict, logger, **_) -> list[dict] | None:
    ...
```

Return value:

* `None` / `[]` → no issues
* Otherwise list of dicts with at least:

  * `row_index: int`
  * `message: str`
  * optional: `severity`, `code`, `meta`

Constraints:

* Validators MUST NOT mutate table values.
* `row_index` must be within `[0, table.height)`.

This deliberately drops the multi-shape v2 formats to reduce engine branching and normalization code.

---

# 7) Pipeline sketch (end-to-end)

Per detected table:

1. Detect region (existing logic)
2. Extract headers + rows (existing logic)
3. Materialize `table: pl.DataFrame` (minimal header normalization)
4. Compute mapping (existing logic)
5. Apply mapping as `table.rename(rename_map)` (with collision skipping)
6. `on_table_mapped` (may replace table)
7. Run transforms (DataFrame-native)
8. `on_table_transformed` (may replace table)
9. Run validators → produce `issues_patch` + flattened `issues`
10. `on_table_validated` (may replace table; columns only)
11. If `remove_unmapped_columns=True`, drop non-canonical columns
12. Write `table` to output worksheet
13. `on_table_written` (formatting/summaries)

---

# 8) Implementation plan (touchpoints + steps)

## 8.1 Expected file touchpoints (update as you go)

```text
apps/ade-engine/src/ade_engine/infrastructure/settings.py                 # remove_unmapped_columns; remove append_unmapped_columns + unmapped_prefix
apps/ade-engine/src/ade_engine/models/extension_contexts.py               # DF-only contexts and new callable types
apps/ade-engine/src/ade_engine/extensions/registry.py                     # hook return composition for table hooks
apps/ade-engine/src/ade_engine/application/pipeline/pipeline.py           # materialize table DF; mapping-as-rename; stage wiring; remove on_table_detected
apps/ade-engine/src/ade_engine/application/pipeline/transform.py          # v3 transform runner (Expr/dict[Expr])
apps/ade-engine/src/ade_engine/application/pipeline/validate.py           # v3 validator runner (list of row-indexed issues)
apps/ade-engine/src/ade_engine/application/pipeline/render.py             # write directly from pl.DataFrame; apply remove_unmapped_columns pre-write
apps/ade-engine/docs/*                                                    # rewrite docs for DF-first contracts and stage semantics
apps/ade-engine/src/ade_engine/extensions/templates/config_packages/default/  # update template settings + examples
apps/ade-engine/tests/                                                    # focused tests for mapping rename, hook replacement, drop-unmapped, v3 transforms/validators
```

## 8.2 Steps (in order)

1. **Settings cleanup**

   * Add `remove_unmapped_columns` (default `false`)
   * Delete `append_unmapped_columns` and `unmapped_prefix`

2. **Stage cleanup**

   * Remove `on_table_detected` (code + docs + templates)
   * Ensure hook names and ordering match the new lifecycle

3. **Materialize single DataFrame**

   * Build `table: pl.DataFrame` immediately after extraction
   * Delete internal “column store” representation in the pipeline

4. **Mapping-as-rename**

   * Convert mapping output into a rename plan
   * Apply renames with collision skipping + warnings

5. **Hook engine updates**

   * Table hooks accept/return DataFrames (priority-ordered composition)

6. **Transforms v3**

   * Implement transform runner with restricted return types (Expr / dict[Expr])
   * Apply via `with_columns` in registry order

7. **Validators v3**

   * Implement validator runner returning list of row-indexed issues
   * Build `issues_patch`/`issues` from a single normalized shape

8. **Write from DataFrame**

   * Apply `remove_unmapped_columns` immediately before render
   * Render headers + values directly from `table`

9. **Docs + template package**

   * Update hook docs, callable contracts, pipeline narrative
   * Update default templates to demonstrate the new simplest patterns

10. **Focused tests**

* Mapping rename behavior (including collision skip)
* Hook replacement composition
* `remove_unmapped_columns` behavior
* Transform Expr + multi-output derived fields
* Validator list-of-issues normalization + bounds enforcement
* Guarantee: written table == table passed into `on_table_written`

---

# 9) Acceptance criteria

This work package is done when:

* The engine creates exactly **one** `pl.DataFrame` per detected table and uses it end-to-end.
* Mapping is implemented as deterministic **column renames** on that same DataFrame.
* “Unmapped columns” are simply columns that remain with extracted names.
* `remove_unmapped_columns=false` writes unmapped columns by default; `true` drops non-canonical columns immediately before write.
* Hooks always receive `table: pl.DataFrame`; only allowed stages can replace it by return value.
* Transforms and validators are DataFrame-native and no longer expose `TableData`/`TableView` or list-vector contracts.
* The DataFrame written to the worksheet matches the one provided to `on_table_written`.
* Docs, template config package, and tests reflect the new contracts and behavior.

---

# 10) Notes / intentional trade-offs (call out explicitly)

* This refactor trades “engine magic” (passthrough stitching, special ordering rules, dual table views) for **predictability and simplicity**.
* Output column ordering becomes “whatever `table.columns` is at write time”; configs can enforce ordering in `on_table_validated`.
* Mapping conflicts are handled deterministically by skipping conflicting renames (and logging), rather than inventing suffixed canonical names.
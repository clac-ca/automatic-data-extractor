> **Agent instruction (read first):**
>
> * Treat this work package as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * If you must change the plan, **update this document first**, then the code.

---

# Work Package: `ade-engine-refactor` — Single-Table DataFrame Pipeline + Inline Validation

## What we’re doing (plain terms)

ADE should feel like: **“I’m just working with a normal table.”**

Today, the engine constructs and threads stage-specific internal table objects (`TableData` / `TableView`) through mapping, transforms, validation, and rendering. That creates:

* stage-dependent shapes,
* unclear mutability,
* extension contracts that leak engine internals,
* and a lot of glue code (column stores, unmapped passthrough stitching, prefixes, “issue patch” alignment, etc.).

### The redesign

We refactor ADE so that each detected table is **exactly one** Polars DataFrame:

* The engine materializes `table: pl.DataFrame` immediately after extraction.
* That same `table` flows end-to-end: mapping → hooks → transforms → hooks → validation → hooks → write → hooks.
* Mapping is a **column rename step** on `table`, nothing else.
* Transformations are **Polars expressions** applied to `table`.
* **Validation is inline**: validators write per-field (and optionally per-row) issue messages into reserved columns on `table`.
  That means issues automatically stay aligned under filtering/sorting/reordering.

This is a **deliberate breaking change** with **no backward compatibility**. We are removing legacy contracts and deleting dead surfaces in one sweep.

---

## Why this is a big simplification

### What disappears

* `TableData` / `TableView` pipeline objects
* stage-dependent table shapes and “what can I mutate when?”
* “append unmapped columns” render modes and passthrough stitching
* issue patch merging / row-index alignment complexity
* “don’t reorder rows after validation” restrictions (no longer needed)

### What replaces it

* one DataFrame
* one way to change it: return a new DataFrame from allowed hook stages
* transforms = expressions
* validators = expressions that produce message columns
* renderer writes exactly what it sees (minus reserved columns unless configured)

---

## Breaking change policy

* **No adapters. No dual-mode. No compatibility shims.**
* Existing config packages must update.
* Docs + default template config package must be updated together with engine changes.
* Legacy code paths and old extension surfaces are deleted.

---

## Work Package Checklist

* [x] Commit to “one DataFrame per table” end-to-end in pipeline
* [x] Implement header normalization (safe + deterministic)
* [x] Implement mapping-as-rename (safe + deterministic collision handling)
* [x] Remove `TableData` / `TableView` models and all legacy extension contracts
* [x] Remove `on_table_detected` everywhere (code + docs + templates)
* [x] Implement hook stages with return-DataFrame composition:

  * `on_table_mapped` → `on_table_transformed` → `on_table_validated` → `on_table_written`
* [x] Implement transform v3 contract (Expr / dict[str, Expr]) + runner
* [x] Implement validator v3 contract (Expr messages) + inline issue columns
* [x] Add engine-reserved “inline validation” columns and rules (drop from output by default)
* [x] Implement “drop non-canonical columns” setting: `remove_unmapped_columns` (default false)
* [x] Update renderer to write directly from DataFrame + apply dropping rules
* [x] Update docs (hooks, callable contracts, pipeline narrative, examples)
* [x] Update template config package (hooks/transforms/validators examples)
* [x] Add focused tests for the new pipeline and contracts
* [x] Delete legacy settings (`append_unmapped_columns`, `unmapped_prefix`, etc.) and related logic

---

# 1) Core principles & invariants

## 1.1 Single-table invariant

For each detected table region, the engine creates **exactly one** DataFrame:

* `table: pl.DataFrame`

No other table-shaped artifact exists in the public extension surface.

Engine metadata (region, mapping confidences, etc.) may exist in context, but **table values live only in `table`.**

## 1.2 Mutability model

* Polars DataFrames are immutable → any table modification produces a new DataFrame.
* The engine only accepts table replacement (return a new `table`) from specific hook stages.

## 1.3 Reserved column prefix

The engine reserves a prefix for internal columns:

* `__ade_...`

Rules:

* Config authors must not create canonical fields starting with `__ade_`.
* The engine may add / overwrite reserved columns during validation.
* Reserved columns are **not written** to the output workbook by default (configurable).

---

# 2) Table extraction and header normalization

## 2.1 DataFrame materialization boundary

Immediately after extracting a region (header row + data rows), the engine builds:

* `table = pl.DataFrame(rows, schema=normalized_header_names)`

* Rows are the detected data rows (excluding the header row).

* Column names are derived from extracted headers using **minimal normalization** to satisfy Polars.

## 2.2 Minimal header normalization algorithm

Headers can be empty, duplicated, or non-string. Polars requires unique, non-empty strings.

For each source column index `i`:

1. `base = str(header).strip()` if header is non-empty, else `f"col_{i+1}"`
2. If `base == ""`, use `f"col_{i+1}"`
3. Deduplicate collisions in source order by suffix:

   * `"<base>__2"`, `"<base>__3"`, …

This preserves “rawness” while ensuring a valid DataFrame.

---

# 3) Mapping is column rename (and nothing else)

## 3.1 Mapping behavior

Mapping produces a rename plan and applies it to the same DataFrame:

* For each mapped source column:

  * rename extracted column name → canonical field name
* Unmapped columns:

  * remain as-is
  * remain in the DataFrame

There is no “canonical table construction” and no “passthrough table”.

## 3.2 Collision handling (deterministic)

Mapping must not create duplicate column names.

If renaming an extracted column to a canonical field name would collide with an existing column name:

* Skip that rename
* Keep the extracted name
* Emit a warning with details

This avoids inventing suffixed canonical names (which complicates transforms/validators keyed by field).

---

# 4) Output column policy: unmapped columns are default

## 4.1 Setting: `remove_unmapped_columns`

Replace old passthrough settings with one boolean:

* `remove_unmapped_columns: bool = false` (default)

Behavior:

* `false` → write all non-reserved columns present in `table`
* `true` → before write, drop any non-reserved column whose name is not a registered canonical field

This makes “passthrough” the default, and “schema-only output” an opt-in.

## 4.2 Reserved columns are not written by default

Before writing:

* drop all columns starting with `__ade_`

Optionally allow:

* `write_diagnostics_columns: bool = false` (default false)

If `true`, reserved columns may be written (primarily for debugging exports).

---

# 5) Hook stages (simple and stable)

We standardize the table hook stages to four:

1. `on_table_mapped` (post-mapping, pre-transform)
2. `on_table_transformed` (post-transform, pre-validation)
3. `on_table_validated` (post-validation, pre-write)
4. `on_table_written` (post-write; output workbook formatting)

We remove `on_table_detected`.

## 5.1 Hook return semantics

* Hooks run in priority order.
* If a hook returns a DataFrame, it becomes the input to the next hook in that stage.
* If it returns `None`, the table is unchanged.

## 5.2 What each stage may do

### `on_table_mapped`

* Can replace `table`
* Can filter/sort/reorder columns

### `on_table_transformed`

* Can replace `table`
* Can filter/sort/reorder columns

### `on_table_validated`

* Can replace `table`
* Can filter/sort/reorder columns (now safe because validation is inline)
* Intended for final shaping: ordering, dropping columns, adding output-only computed columns

### `on_table_written`

* No table replacement
* Can edit output workbook/sheet (formatting, summaries, extra sheets)
* Must not alter the data table values (already written)

**Key change:** Because issues are stored inline as columns, we no longer need a “no row ops after validation” restriction.

---

# 6) New callable contracts (v3)

## 6.1 Transform contract (v3)

Transforms operate on the DataFrame and return Polars expressions.

### Signature (recommended)

```py
def transform(
    *,
    field_name: str,
    table: pl.DataFrame,
    state: dict,
    metadata: dict,
    logger,
    **_
) -> pl.Expr | dict[str, pl.Expr] | None:
    ...
```

### Return types

* `None`: no change
* `pl.Expr`: replacement expression for `field_name`
* `dict[str, pl.Expr]`: multi-output (e.g., splitting a name)

### Constraints

* Transform runner must not change row count.
* Output columns must be valid names (strings, non-empty) and non-reserved unless explicitly creating diagnostics.
* Any derived outputs intended as canonical fields should be registered.

### Example: normalize phone number

```py
import polars as pl

def normalize_phone(*, field_name: str, table: pl.DataFrame, **_):
    # Remove non-digits, keep as string.
    return (
        pl.col(field_name)
        .cast(pl.Utf8)
        .str.replace_all(r"\D", "")
        .str.strip()
    )
```

### Example: split full name into normalized full/first/last

```py
import polars as pl

def split_full_name(*, field_name: str, table: pl.DataFrame, **_):
    full = pl.col(field_name).cast(pl.Utf8).str.strip()

    # Simple split; production logic can be richer.
    parts = full.str.split(" ")

    return {
        "full_name": full,
        "first_name": parts.list.get(0),
        "last_name": parts.list.get(-1),
    }
```

**Engine behavior:** collect all expressions and apply using `table.with_columns(...)`.

---

## 6.2 Inline validation contract (v3)

Validators do not return “issue patches” or row-indexed structures.
They return **an expression that evaluates to either null (valid) or a message (invalid).**

### Signature (recommended)

```py
def validate(
    *,
    field_name: str,
    table: pl.DataFrame,
    state: dict,
    metadata: dict,
    logger,
    **_
) -> pl.Expr | None:
    ...
```

### Return types

* `None`: no issues for this validator
* `pl.Expr`: produces `Utf8 | Null` per row

### Where issues go

For each validated field `field_name`, the engine writes:

* `__ade_issue__{field_name}`: `Utf8 | Null`

Optionally compute:

* `__ade_has_issues`: `Boolean` (any issue column is non-null)
* `__ade_issue_count`: `Int32` (# of non-null issue columns)

### Example: validate phone length

```py
import polars as pl

def validate_phone(*, field_name: str, table: pl.DataFrame, **_):
    v = pl.col(field_name).cast(pl.Utf8)

    return (
        pl.when(v.is_null() | (v.str.len_chars() < 10))
        .then(pl.lit("Invalid phone number"))
        .otherwise(pl.lit(None))
    )
```

### Example: validate first/last name presence

```py
import polars as pl

def validate_name_parts(*, field_name: str, table: pl.DataFrame, **_):
    # Example validator for "first_name"
    v = pl.col(field_name).cast(pl.Utf8).str.strip()

    return (
        pl.when(v.is_null() | (v == ""))
        .then(pl.lit("Missing value"))
        .otherwise(pl.lit(None))
    )
```

### Why this is better

* Validators don’t need row numbers.
* Issues automatically stay aligned through filtering/sorting/reordering because they live in the same row.
* Hooks can safely reshape after validation without breaking issue alignment.

---

# 7) Renderer behavior (write from DataFrame)

## 7.1 What gets written

At write time, the engine builds `write_table` from `table`:

1. Start with current `table`
2. If `remove_unmapped_columns=True`:

   * drop any non-reserved column not in the canonical registry
3. Drop reserved columns (`__ade_*`) unless `write_diagnostics_columns=True`
4. Write headers + values directly to the output worksheet

**Critical invariant:** The DataFrame passed into `on_table_written` is the one that was written (or a clearly defined “write_table” if we drop reserved columns—pick one and document it).

Recommendation for clarity:

* Keep `table` unchanged in memory
* Derive `write_table = table.drop(reserved)` and pass **both** to `on_table_written`:

  * `table` (full, includes issues)
  * `write_table` (what was written)
    This makes formatting hooks trivial and avoids confusion.

---

# 8) Pipeline sketch (end-to-end)

Per detected table:

1. Detect region (existing)
2. Extract header + rows (existing)
3. Materialize `table: pl.DataFrame` (minimal header normalization)
4. Compute mapping diagnostics (existing)
5. Apply mapping as rename (new)
6. `on_table_mapped(table=...)` → may replace
7. Apply transforms v3 (`Expr` / `dict[str, Expr]`) → new table
8. `on_table_transformed(table=...)` → may replace
9. Apply validators v3 → write `__ade_issue__*` columns inline; compute summary columns
10. `on_table_validated(table=...)` → may replace
11. Derive `write_table` by applying:

    * `remove_unmapped_columns`
    * reserved-column dropping
12. Write `write_table` to worksheet
13. `on_table_written(table=table, write_table=write_table, ...)` → formatting/summaries

---

# 9) Implementation plan (touchpoints + step order)

## 9.1 Expected file touchpoints

```text
apps/ade-engine/src/ade_engine/infrastructure/settings.py
  - add remove_unmapped_columns (default false)
  - add write_diagnostics_columns (optional, default false)
  - delete append_unmapped_columns, unmapped_prefix, legacy options

apps/ade-engine/src/ade_engine/models/extension_contexts.py
  - new DF-only context types
  - remove TableData/TableView from public surfaces
  - include write_table in on_table_written context (recommended)

apps/ade-engine/src/ade_engine/extensions/registry.py
  - new registration for v3 transforms/validators (Expr-based)
  - hook invocation supports return-DataFrame composition

apps/ade-engine/src/ade_engine/application/pipeline/pipeline.py
  - materialize one pl.DataFrame immediately after extraction
  - mapping-as-rename
  - new hook stage wiring
  - remove on_table_detected

apps/ade-engine/src/ade_engine/application/pipeline/transform.py
  - v3 transform runner:
    - call transforms
    - normalize outputs (Expr or dict[str, Expr])
    - apply with_columns

apps/ade-engine/src/ade_engine/application/pipeline/validate.py
  - v3 validator runner:
    - call validators
    - write __ade_issue__{field} columns
    - compute __ade_has_issues / __ade_issue_count

apps/ade-engine/src/ade_engine/application/pipeline/render.py
  - write directly from DataFrame
  - apply remove_unmapped_columns + reserved-column drop rules

apps/ade-engine/docs/
  - rewrite hooks.md, callable-contracts.md, architecture.md, pipeline-and-registry.md
  - include examples (phone normalize, full name split, inline validation)

apps/ade-engine/src/ade_engine/extensions/templates/config_packages/default/
  - update templates to v3 hooks/transforms/validators
  - remove legacy examples

apps/ade-engine/tests/
  - focused tests for:
    - header normalization
    - mapping rename collisions
    - hook return composition
    - transform multi-output
    - inline issue columns survive filter/sort
    - remove_unmapped_columns at write
    - written output equals write_table
```

## 9.2 Step order (do in this sequence)

1. **Settings cleanup**

   * Add `remove_unmapped_columns`
   * (Optional) Add `write_diagnostics_columns`
   * Delete old passthrough settings and dead code

2. **Delete legacy table models**

   * Remove `TableData` / `TableView` usage from extensions
   * Delete extension context references

3. **Single DataFrame materialization**

   * Implement header normalization
   * Create `table: pl.DataFrame` immediately after extraction

4. **Mapping-as-rename**

   * Generate rename map
   * Apply with collision skip + warning

5. **Hook system update**

   * Remove `on_table_detected`
   * Add/ensure `on_table_mapped`, `on_table_transformed`, `on_table_validated`, `on_table_written`
   * Enable hook return-DataFrame composition

6. **Transforms v3 runner**

   * Implement Expr / dict[str, Expr]
   * Apply with `with_columns`

7. **Validators v3 inline**

   * Implement validators returning issue-message expressions
   * Write `__ade_issue__*` columns
   * Add `__ade_has_issues` / `__ade_issue_count`

8. **Render from DataFrame**

   * Implement write_table derivation
   * Write headers + cells directly from `write_table`

9. **Templates + docs**

   * Update config template and docs to new contracts
   * Include examples and new reserved-column rules

10. **Tests**

* Add tests that specifically demonstrate:

  * issues remain aligned after filtering/sorting post-validation
  * multi-output transform works
  * remove_unmapped_columns behavior

---

# 10) Acceptance criteria

This refactor is done when:

* The pipeline materializes exactly one `pl.DataFrame` per detected table and uses it end-to-end.
* Mapping is implemented as rename-only on that DataFrame.
* Hooks receive `table: pl.DataFrame` consistently and may replace it only by returning a new DataFrame.
* Transforms use the v3 contract (Expr / dict[str, Expr]) and no longer expose list-vector contracts.
* Validators use the v3 inline contract (issue-message expressions) and produce reserved `__ade_issue__*` columns.
* Validation issues stay correct under filtering/sorting/reordering because they live inline in the table.
* Renderer writes directly from DataFrame and respects:

  * `remove_unmapped_columns`
  * reserved-column dropping (unless `write_diagnostics_columns=True`)
* Docs and the default template package reflect the new design.
* Legacy code (TableData/TableView + old settings + old contracts) is fully deleted.

---

# Appendix: Template examples (drop-in snippets)

## A) Hook: drop invalid rows after validation (now safe)

```py
import polars as pl

def on_table_validated(*, table: pl.DataFrame, **_):
    # Keep only rows with no issues
    if "__ade_has_issues" in table.columns:
        return table.filter(~pl.col("__ade_has_issues"))
    return table
```

## B) Hook: reorder columns for output

```py
def on_table_validated(*, table: pl.DataFrame, **_):
    desired = [c for c in ["full_name", "first_name", "last_name", "phone"] if c in table.columns]
    remaining = [c for c in table.columns if c not in desired]
    return table.select(desired + remaining)
```

## C) Format cells with issues in `on_table_written`

```py
def on_table_written(*, table, write_table, sheet, workbook, **_):
    # Example: if __ade_issue__phone is non-null, color the phone cell.
    # (Exact mapping of DF columns → worksheet columns depends on render implementation.)
    pass
```

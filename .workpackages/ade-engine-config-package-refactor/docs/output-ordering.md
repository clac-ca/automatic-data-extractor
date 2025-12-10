# Output column ordering (ADE Engine)

This document defines **how ADE orders columns in the exported workbook** in the ADE Engine architecture (registry-based config packages, no manifest column ordering).

## Goals

1. **Dead simple default**: output order should “just make sense” without extra config.
2. **No column-order config to maintain**: avoid a separate “order list” source of truth.
3. **Still flexible**: advanced users can reorder columns via a hook.

---

## Definitions

* **Input table**: The detected table extracted from a sheet (headers + rows), with columns in a concrete left→right order.
* **Mapped column**: An input column that ADE successfully mapped to a known **Field** (e.g., `email`, `first_name`).
* **Unmapped column**: An input column that ADE did not map to any Field (or lost during conflict resolution).
* **Output table**: The rendered table ADE writes to the output workbook.

---

## Default ordering rule (the new standard)

### Rule

**Output columns are written in the same left-to-right order as the input table’s columns.**

* For **mapped** input columns: output uses the mapped **field name** as the output column header.
* For **unmapped** input columns:

  * If `append_unmapped_columns = true`, ADE appends them to the **far right** (after all mapped output columns).
  * If `append_unmapped_columns = false`, unmapped columns are **dropped** from the output (but still available in diagnostics / hook contexts).

This means the default output is “what the user gave you,” but normalized into your canonical fields, plus optional raw spillover on the right.

---

## Algorithm (step-by-step)

Assume ADE has already produced:

* `input_columns`: a list of input columns in original order (index 0..N-1)
* `mapping`: a one-to-one mapping result (at most one input column per field)

  * Example: column 2 → `email`, column 5 → `first_name`, etc.
* `unmapped`: list of input columns with no mapped field (including “losers” from conflict resolution)

Then:

1. **Build mapped output list in input order**

   * Iterate input columns from left to right.
   * If column is mapped → emit output column with header = `field.name`.
2. **Optionally append unmapped**

   * If `append_unmapped_columns`:

     * Iterate `unmapped` columns (still in their input order).
     * Emit output column header = `unmapped_prefix + <original_header_or_fallback>`.

### Header naming for unmapped columns

Unmapped output columns must have stable, human-debuggable names:

* If the input column has a header string:
  `raw_<header>` (sanitized to a safe identifier)
* If not:
  `raw_col_<index>`

Where:

* `unmapped_prefix` defaults to `raw_` (engine setting).

---

## Examples

### Example A: basic mapping + unmapped appended

**Input columns (left→right):**

1. `First Name`
2. `Employee Email`
3. `Favorite Color`

**Mapping results:**

* `First Name` → `first_name`
* `Employee Email` → `email`
* `Favorite Color` → unmapped

**Output (append_unmapped_columns=true, unmapped_prefix="raw_"):**

1. `first_name`
2. `email`
3. `raw_favorite_color`

### Example B: unmapped dropped

Same input/mapping as above.

**Output (append_unmapped_columns=false):**

1. `first_name`
2. `email`

### Example C: input order preserved even if “canonical order” differs

**Input:**

1. `Email`
2. `Last Name`
3. `First Name`

**Output:**

1. `email`
2. `last_name`
3. `first_name`

No reordering happens by default. If a business wants `first_name,last_name,email`, that is a **hook concern** (below).

---

## Conflict policy (duplicate candidates)

Sometimes two input columns can compete for the same field (e.g., two “Email” columns).

In ADE Engine, the expectation is that the **mapping stage produces a one-to-one assignment**:

* The “winning” input column for a field is chosen by highest score; if scores tie, the engine uses `mapping_tie_resolution` (`leftmost` default; `drop_all` leaves all tied columns unmapped).
* The “losing” column becomes **unmapped** and follows the unmapped handling rules.

This prevents silent overwrites and keeps output headers unique while leaving the exact conflict rule to the final pipeline decision.

---

## How to reorder output columns (advanced, via hook)

If you want a custom output order (e.g., canonical order for downstream systems), do it in a hook rather than config ordering.

**Recommended hook point:** `HookName.ON_TABLE_MAPPED`

At this point:

* ADE has a mapping
* You can reorder output columns, patch mapping, or add additional derived columns

### What it looks like (conceptual)

```python
from ade_engine.registry.decorators import hook
from ade_engine.registry.models import HookName, HookContext

@hook(HookName.ON_TABLE_MAPPED)
def enforce_canonical_column_order(ctx: HookContext) -> None:
    table = ctx.table
    if table is None:
        return

    canonical = [
        "first_name",
        "last_name",
        "email",
        "member_id",
    ]

    def sort_key(col):
        if col.field_name in canonical:
            return (0, canonical.index(col.field_name))
        return (1, col.source_index)

    table.columns.sort(key=sort_key)
```

### Minimal API expectation

To keep this intuitive, the engine should expose a small, obvious surface on the table object used by hooks:

* `table.output_columns` (a list you can reorder)
* or a helper method like:

  * `table.reorder_output_columns(...)`
  * `table.set_output_order([...])`

The hook should be able to do the reorder without needing to understand internal render logic.

---

## Settings that control output behavior

These are **engine settings** (loaded via `.env`, env vars, optional TOML), not config-package manifest values:

* `append_unmapped_columns: bool`

  * Default: `true` (recommended)
* `unmapped_prefix: str`

  * Default: `raw_`

This keeps “writer behavior” consistent across runs and avoids duplicating it across config packages.

---

## Practical guidance (what we recommend)

* **Default**: preserve input order + append unmapped.

  * It feels natural, reduces configuration, and avoids “surprise reshuffles.”
* **Only reorder when needed**:

  * If a downstream system requires a strict schema order, enforce it via `ON_TABLE_MAPPED`.
* **Keep unmapped**:

  * Appending unmapped columns to the right is a strong debugging affordance and helps adoption.

---

## Notes for implementers (where this lives)

* The ordering logic should live in the **render/write stage** (e.g., `pipeline/render.py`), using:

  * input table column order
  * final mapping result
  * Settings: `append_unmapped_columns`, `unmapped_prefix`
* Hooks can modify the output plan before render finalizes.

---

## FAQ

**Q: Why not keep a “column_order” list in config?**
Because it becomes a second source of truth that constantly drifts, especially with a GUI editor and evolving detector sets. The hook-based approach is both simpler and more powerful.

**Q: Will users lose the ability to reorder columns?**
No. They can reorder via `HookName.ON_TABLE_MAPPED` (or `ON_TABLE_WRITTEN` if they want to manipulate the workbook directly, but that’s less clean).

**Q: What if we want unmapped columns kept where they were originally?**
That’s a different mode. ADE Engine’s default is “mapped in place, unmapped appended.” If you need “original layout preserved,” that can be a hook or a future optional setting.

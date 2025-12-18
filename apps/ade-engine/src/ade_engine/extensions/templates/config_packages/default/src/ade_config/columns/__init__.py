"""ADE config package: column modules (`ade_config.columns`)

Convention (recommended)
------------------------
- One module per canonical field (e.g. `email.py`).
- Each module defines `register(registry) -> None` and typically registers:
  - a `FieldDef` (the canonical field)
  - (enabled by default) a simple header-name detector
  - optional examples (value detectors / transforms / validators), commented out

Pipeline stages (mental model)
------------------------------
- Column detectors run BEFORE mapping and return score patches: `{field: score}`.
- Column transforms/validators run AFTER mapping, operating on canonical field names.

Calling convention
------------------
The engine expands context objects into keyword arguments when calling your functions.
You can declare *only the parameters you use* (e.g., just `field_name`), and ignore the rest.

Polars expressions (pl.Expr) primer
----------------------------------
Transforms/validators return `pl.Expr`, which is a *deferred, vectorized* expression.
Think “SQL expression”, not “Python value”.

Common building blocks:
- `pl.col("name")` references a column
- `pl.lit("x")` makes a literal (important: plain `"x"` can be treated like a column name)
- `pl.when(cond).then(expr).otherwise(expr)` is a vectorized if/else
- `pl.coalesce([a, b, ...])` picks the first non-null

Tip: When prototyping in a scratch notebook, remember to alias:
`df.with_columns(expr.alias("my_field"))`.

The top-level `ade_config.register()` auto-discovers and registers these modules.
"""

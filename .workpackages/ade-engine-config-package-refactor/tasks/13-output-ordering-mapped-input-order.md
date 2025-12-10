# Task 13 – Output ordering: mapped columns keep input order

Checklist: D) Implement output ordering rule — mapped columns in **input column order**.

Objective: Ensure render step preserves original column index order for mapped fields by default.

Implementation steps:
- [ ] In `pipeline/render.py` (or writer), carry forward each mapped column’s source index during detection/mapping.
- [ ] Sort mapped output columns by `source_index` before writing; only override if a hook has already mutated order.
- [ ] Add unit/component test asserting output order matches input order when hooks absent.
- [ ] Update docs `docs/output-ordering.md` to reflect engine-owned default.

Code example:
```py
mapped_cols_sorted = sorted(mapped_cols, key=lambda col: col.source_index)
writer.write_columns(mapped_cols_sorted)
```

Definition of done:
- [ ] Default output for mapped fields mirrors input ordering; documented and tested.

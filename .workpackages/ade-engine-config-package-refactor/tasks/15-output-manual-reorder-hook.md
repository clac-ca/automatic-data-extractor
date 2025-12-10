# Task 15 – Manual reorder path via hook

Checklist: D) Add supported “manual reorder” path via hook (recommended: `HookName.ON_TABLE_MAPPED`).

Objective: Provide hook-based extension point to reorder output columns without manifest order config.

Implementation steps:
- [ ] In pipeline, after mapping and before transforms, call `ON_TABLE_MAPPED` hooks with a table object exposing `columns` list that can be reordered in place.
- [ ] Document helper pattern in `docs/hooks.md` and `docs/output-ordering.md`; include code sample similar to template reorder in `config_package_example/hooks/on_table_mapped.py` or `on_table_written.py`.
- [ ] Ensure downstream render respects modified column order (skip resorting if hook sets custom order).

Code example:
```py
@hook(HookName.ON_TABLE_MAPPED)
def reorder(ctx: HookContext):
    desired = ["email", "first_name", "last_name"]
    ctx.table.columns.sort(key=lambda col: (0, desired.index(col.field_name)) if col.field_name in desired else (1, col.source_index))
```

Definition of done:
- [ ] Hook sees mapped table, can reorder; renderer preserves hook order; docs show supported approach.

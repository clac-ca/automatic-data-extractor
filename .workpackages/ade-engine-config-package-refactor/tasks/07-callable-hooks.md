# Task 07 – Callable contract: Hooks (HookName)

Checklist: B) Define and document **Hooks** contract (HookName).

Objective: Enumerate hook names, contexts, and decorator usage; ensure registry handles hook registration and ordering.

Implementation steps:
- [ ] Define `HookName` enum with `ON_WORKBOOK_START`, `ON_SHEET_START`, `ON_TABLE_DETECTED`, `ON_TABLE_MAPPED`, `ON_TABLE_WRITTEN`, `ON_WORKBOOK_BEFORE_SAVE` in `registry/models.py`.
- [ ] Add `HookContext` struct carrying run/state plus optional workbook/sheet/table/logger depending on stage.
- [ ] `@hook(hook_name, priority=0)` decorator registers into `registry.hooks[hook_name]` with deterministic ordering.
- [ ] Document mutation-in-place expectation (no return value required) and recommended reorder hook usage in `docs/hooks.md` + `docs/callable-contracts.md`.

Code example:
```py
@hook(HookName.ON_TABLE_MAPPED, priority=0)
def reorder(ctx: HookContext):
    table = ctx.table
    if not table:
        return
    desired = ["email", "first_name", "last_name"]
    table.columns.sort(key=lambda col: (0, desired.index(col.field_name)) if col.field_name in desired else (1, col.source_index))
```

Definition of done:
- [ ] HookName enum exported; decorator uses active registry; docs and template hooks align (see `config_package_example/src/ade_config/hooks`).

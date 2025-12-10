# Task 12 – Pipeline refactor: hook execution via Registry

Checklist: C) Refactor hook execution to use Registry hooks (HookName); remove old dispatcher/protocol if redundant.

Objective: Centralize hook invocation using registry.hooks with deterministic ordering and context objects.

Implementation steps:
- [ ] Replace custom dispatcher/protocol with simple loop over `registry.hooks[hook_name]` within pipeline stages.
- [ ] Build `HookContext` per stage (table/sheet/workbook as applicable) and pass to hook functions; expect in-place mutation.
- [ ] Decide exception policy (fail fast for hooks by default) and implement consistent logging.
- [ ] Remove legacy hook dispatcher files and references.

Code example:
```py
ctx = HookContext(run=run_ctx, state=state, table=table, logger=logger)
for hook_def in registry.hooks[HookName.ON_TABLE_MAPPED]:
    hook_def.fn(ctx)
```

Definition of done:
- [ ] Hooks invoked only via registry; ordering priority/module/qualname; old dispatcher removed.

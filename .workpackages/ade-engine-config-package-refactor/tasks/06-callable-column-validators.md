# Task 06 – Callable contract: Column Validators

Checklist: B) Define and document **Column Validators** contract (return validation result dict or list; `cell_validator` sugar aggregates per-cell).

Objective: Standardize validator shape and engine normalization for reporting-only validation.

Implementation steps:
- [ ] Define `ValidateContext(field_name, values, state, run, logger)`; optionally include column_index in context.
- [ ] Validators return either a dict with `passed: bool` (+ optional message/row_index/column_index/value) or a list of such dicts; normalize into a flat list for reporting.
- [ ] Provide `cell_validator` sugar to run per cell and aggregate results.
- [ ] Ensure validators cannot mutate mapping/output; reporting only.
- [ ] Document in `docs/callable-contracts.md` and in template docs; adjust examples to use the normalized shape.

Code example:
```py
@column_validator(field="email")
def validate_email(ctx: ValidateContext):
    issues = []
    for idx, v in enumerate(ctx.values):
        if v and "@" not in str(v):
            issues.append({"passed": False, "message": "Invalid email", "row_index": idx, "value": v})
    return issues or {"passed": True}
```

Definition of done:
- [ ] Normalization helper in engine; docs updated; template validators match contract.

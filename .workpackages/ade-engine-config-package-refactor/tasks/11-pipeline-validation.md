# Task 11 – Pipeline refactor: validation via Registry column validators

Checklist: C) Refactor validation step to use Registry column validators (reporting only).

Objective: Execute validators registered per field, aggregate issues, and keep data intact.

Implementation steps:
- [ ] For each mapped field, build `ValidateContext` (values, field_name, state, run, logger, optional column_index).
- [ ] Iterate `registry.column_validators` for that field in sorted order; normalize outputs to a flat list of validation result dicts; append to run issues.
- [ ] Do not mutate data based on validation failures; ensure exceptions are captured/logged.
- [ ] Remove manifest/protocol wiring from validation step.

Code example:
```py
ctx = ValidateContext(run=run_ctx, state=state, field_name=field, values=col_values, logger=logger)
for val in registry.validators_for(field):
    results = normalize_validation_output(val.fn(ctx))
    issues.extend(r for r in results if not r.get("passed", False))
```

Definition of done:
- [ ] Validators run through registry-only path; issues are reported without altering transformed data; component tests cover failure reporting.

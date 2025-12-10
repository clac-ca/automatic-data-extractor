# Task 05 – Callable contract: Column Transforms

Checklist: B) Define and document **Column Transforms** contract (row-aligned list; `cell_transformer` sugar allowed).

Objective: Specify how transforms consume mapped column values and produce normalized rows.

Implementation steps:
- [ ] Define transform signature with `TransformContext(field_name, values, state, run, logger)`.
- [ ] Require return type: row-aligned list matching input length where each item is either a raw value (shorthand for `{current_field: value}`) or a dict including the current field plus optional extra field values.
- [ ] Provide optional `cell_transformer` helper that wraps per-cell logic into a column transform.
- [ ] Document overwrite policy: later transforms in priority order win when setting the same field for a row; log overwrite when it occurs.
- [ ] Capture contract in `docs/callable-contracts.md` and `docs/pipeline-and-registry.md`; mirror in template examples where transforms simply strip/lower strings.

Code example:
```py
@column_transform(field="email", priority=0)
def normalize_email(ctx: TransformContext):
    return [{"email": (str(v).strip().lower() or None)} for v in ctx.values]
```

Definition of done:
- [ ] Engine enforces return-shape normalization; docs reflect behavior; template transforms conform (see `config_package_example/column_detectors/email.py`).

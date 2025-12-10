# Task 04 – Callable contract: Column Detectors

Checklist: B) Define and document **Column Detector** callable contract (field defs optional; engine auto-creates fields; optional `@field_meta`).

Objective: Nail down signature/return semantics and registration rules for column detectors.

Implementation steps:
- [ ] Ensure `@column_detector(field="...")` registers with required field name; auto-create FieldDef with defaults when missing; warn/ignore unknown field keys in patches.
- [ ] Column detector signature uses `ColumnDetectorContext` (header, column_values, column_values_sample, column_index, state, logger).
- [ ] Normalize `ScorePatch`: float applies to declared `field`; dict may boost/penalize multiple fields; drop unknown or non-finite values.
- [ ] Add optional `@field_meta` helper to declare label/required/dtype/synonyms for UI/docs.
- [ ] Document in `docs/callable-contracts.md` and `docs/config-package-conventions.md` with header + value based examples.

Code example:
```py
@field_meta(name="email", label="Email", required=True)
@column_detector(field="email", priority=60)
def detect_email_header(ctx: ColumnDetectorContext) -> ScorePatch:
    header = (ctx.header or "").lower()
    return {"email": 1.0} if "email" in header else 0.0
```

Definition of done:
- [ ] Decorator enforces active registry; patches are normalized; docs and template examples show per-field modules.

References: `docs/registry-spec.md`, `docs/callable-contracts.md`, examples in `config_package_example/src/ade_config/column_detectors/`.

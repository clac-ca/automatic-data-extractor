# Task 03 – Callable contract: Row Detectors

Checklist: B) Define and document **Row Detector** callable contract.

Objective: Specify the signature, context, and return shape for row detectors and ensure registry decorators enforce it.

Implementation steps:
- [ ] Define `RowDetectorContext` (see Task 01) with row_index, row_values, sheet, state, logger, run metadata.
- [ ] Update `@row_detector` decorator to capture `row_kind` default target and priority; tie float patches to that `row_kind`.
- [ ] Normalize returned `ScorePatch` (float or dict) keyed by row kind names; drop unknown keys; ignore non-finite values.
- [ ] Document the contract in `docs/callable-contracts.md` and `docs/registry-spec.md` with examples.

Code example:
```py
@row_detector(row_kind=RowKind.HEADER, priority=20)
def detect_header(ctx: RowDetectorContext) -> ScorePatch:
    tokens = tokenize(ctx.row_values)
    hits = len(tokens & {"email", "name"})
    return {"header": min(1.0, hits / 3), "data": -0.2}
```

Definition of done:
- [ ] Decorator exists and enforces active registry; docs show context fields and return shapes; sample detectors in `config_package_example/row_detectors` align with the contract.

References: `docs/callable-contracts.md`, `docs/summary.md`, `config_package_example/src/ade_config/row_detectors/*.py`.

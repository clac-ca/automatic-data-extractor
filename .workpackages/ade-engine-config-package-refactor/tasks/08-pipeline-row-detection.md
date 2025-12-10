# Task 08 – Pipeline refactor: row detection uses Registry

Checklist: C) Refactor row detection to use Registry row detectors (remove legacy loader usage).

Objective: Replace manifest-driven row detection with registry-driven execution using RowDetectorContext and score patches.

Implementation steps:
- [ ] Update `apps/ade-engine/src/ade_engine/pipeline/detect_rows.py` (or equivalent) to iterate over `registry.row_detectors` in sorted order.
- [ ] Build `RowDetectorContext` per row (include row_index, row_values, sheet, run, state, logger) and call each detector, normalizing `ScorePatch` via registry helper.
- [ ] Accumulate scores per RowKind; pick header row/table bounds deterministically; respect tie policy (documented in settings or defaults).
- [ ] Remove manifest/loader dependencies from this stage; wire settings/registry via pipeline entrypoint.

Code example:
```py
for idx, values in enumerate(sheet.rows):
    ctx = RowDetectorContext(run=run_ctx, state=state, sheet=sheet, row_index=idx, row_values=values, logger=logger)
    for det in registry.row_detectors:
        patch = registry.normalize_patch(det.row_kind, det.fn(ctx))
        score_board.apply(patch)
```

Definition of done:
- [ ] Row detection runs solely from registry entries; legacy manifest loader code removed from this path; tests cover header selection.

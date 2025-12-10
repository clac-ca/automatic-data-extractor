# Task 09 – Pipeline refactor: column detection + mapping via Registry

Checklist: C) Refactor column detection + mapping to use Registry fields + column detectors.

Objective: Drive column scoring/mapping from registry entries, enforce one-to-one mapping, and integrate tie-resolution settings.

Implementation steps:
- [ ] In `pipeline/detect_columns.py` or mapping module, iterate through input columns; build `ColumnDetectorContext` with header, values, sample, indices.
- [ ] For each `registry.column_detectors`, apply normalized patches to a score accumulator keyed by field name; ignore unknown field keys.
- [ ] Perform mapping selection per column: highest-score wins; tie-breaking uses `Settings.mapping_tie_resolution` (`leftmost` default, `drop_all` leaves tied columns unmapped).
- [ ] Ensure registry auto-created fields are materialized before mapping; include logging of score breakdown for observability.
- [ ] Remove legacy manifest/module-string mapping logic.

Code example:
```py
scores = defaultdict(float)
for det in registry.column_detectors:
    patch = registry.normalize_patch(det.field, det.fn(ctx))
    for field, delta in patch.items():
        scores[field] += delta
winner, best = pick_winner(scores, settings.mapping_tie_resolution)
```

Definition of done:
- [ ] Mapping uses registry order and settings; manifest references removed; deterministic tie behavior documented and tested.

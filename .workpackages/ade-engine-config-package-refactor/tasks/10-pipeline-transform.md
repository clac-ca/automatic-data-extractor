# Task 10 – Pipeline refactor: transform stage uses Registry column transforms

Checklist: C) Refactor transform step to use Registry column transforms.

Objective: Execute transforms registered for mapped fields in deterministic order, normalizing return shapes.

Implementation steps:
- [ ] After mapping, build per-field value lists; iterate `registry.column_transforms` filtered by field.
- [ ] Normalize transform output to row-aligned list-of-dicts; merge into row data, logging overwrites when multiple transforms set the same key.
- [ ] Keep transforms pure (no IO) and catch/report exceptions appropriately.
- [ ] Remove manifest-based transform wiring.

Code example:
```py
for tf in registry.column_transforms_for(field):
    rows = normalize_transform_output(field, tf.fn(ctx))
    merge_rows(output_rows, rows)
```

Definition of done:
- [ ] Transform stage depends only on registry; order is priority/module/qualname; validated by component tests.

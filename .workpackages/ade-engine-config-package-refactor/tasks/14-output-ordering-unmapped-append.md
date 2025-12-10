# Task 14 – Output ordering: append unmapped columns right (if enabled)

Checklist: D) Implement output ordering rule — **unmapped columns appended right (if enabled)**.

Objective: When `Settings.append_unmapped_columns` is true, include passthrough columns after mapped columns with prefix.

Implementation steps:
- [ ] Collect unmapped input columns with their source indices; apply header prefix `settings.unmapped_prefix` when writing.
- [ ] Append to output column list after mapped columns; maintain their original relative order.
- [ ] Respect `append_unmapped_columns=False` by dropping these columns from output.
- [ ] Document behavior and prefix rule in `docs/output-ordering.md` and settings docs.

Code example:
```py
if settings.append_unmapped_columns:
    for col in sorted(unmapped, key=lambda c: c.source_index):
        writer.add_column(header=f"{settings.unmapped_prefix}{col.header}", values=col.values)
```

Definition of done:
- [ ] Unmapped passthrough columns appear after mapped columns when enabled; prefixed; covered by component/integration tests.

# Hooks

`HookName` lifecycle points:
- `ON_WORKBOOK_START`
- `ON_SHEET_START`
- `ON_TABLE_DETECTED`
- `ON_TABLE_MAPPED`
- `ON_TABLE_WRITTEN`
- `ON_WORKBOOK_BEFORE_SAVE`

Hooks receive `HookContext` (metadata, state, workbook/sheet/table, input_file_name, logger) and mutate in place.

**Manual reorder**: Do it in `ON_TABLE_MAPPED` by sorting `ctx.table.mapped_columns`.

Example:
```python
from ade_engine.registry import hook, HookName

@hook(HookName.ON_TABLE_MAPPED)
def reorder(ctx):
    desired = ["email", "first_name", "last_name"]
    ctx.table.mapped_columns.sort(
        key=lambda col: (0, desired.index(col.field_name)) if col.field_name in desired else (1, col.source_index)
    )
```

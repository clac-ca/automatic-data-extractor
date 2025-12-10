# Output Ordering

Default rule:
- Mapped columns keep source input order (by source_index).
- If `Settings.append_unmapped_columns` is True, unmapped source columns are appended to the right, keeping their original relative order, and headers prefixed with `Settings.unmapped_prefix`.

Manual reorder: use `HookName.ON_TABLE_MAPPED` to mutate `table.mapped_columns` list.

Examples:
- Input: `Email | Name | Notes`
- Output (default): `email | name | raw_Notes`
- Output (custom hook): reorder to `name | email | raw_Notes`

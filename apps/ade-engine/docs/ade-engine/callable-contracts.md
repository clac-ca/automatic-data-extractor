# Callable Contracts

All config callables are plain functions registered via decorators. Context objects carry run/sheet/table state and a shared `state` dict.

## Row Detectors
- Signature: `fn(ctx: RowDetectorContext) -> ScorePatch`
- `RowDetectorContext`: row_index, row_values, sheet_name, state, run_metadata, logger.
- Return float to boost the declared `row_kind`; dict to adjust multiple row kinds.

## Column Detectors
- Signature: `fn(ctx: ColumnDetectorContext) -> ScorePatch`
- Context: column_index, header, values, sample, sheet_name, state, run_metadata, logger.
- Float applies to declared field; dict may reference multiple fields (unknown dropped).
- Optional `@field_meta` to add labels/required/dtype metadata.

## Column Transforms
- Signature: `fn(ctx: TransformContext) -> list[dict | value]`
- Context: field_name, values, mapping, state, run_metadata, logger.
- Must return a list matching input length; each item raw value (implies `{field: value}`) or dict including current field. `@cell_transformer` sugar wraps per-cell logic.

## Column Validators
- Signature: `fn(ctx: ValidateContext) -> bool | dict | list[dict]`
- Context: field_name, values, mapping, column_index, state, run_metadata, logger.
- Normalized to list of result dicts with `passed` (False entries become issues). `@cell_validator` helper runs per-cell.

## Hooks
- Registered with `@hook(HookName...)`; receive `HookContext` (run_metadata, state, workbook/sheet/table, logger) and mutate in place. No return required.

# Callable Contracts

This is the authoritative contract for every extension callable. Config packages register callables imperatively with `registry.register_*` inside their `register(registry)` entrypoint. Context objects are expanded into keyword arguments by `call_extension`, so authors declare only the parameters they need.

## Row detectors

Context fields you can accept:
- `row_index: int`
- `row_values: Sequence[Any]` — values for that row (trimmed)
- `sheet_name: str`
- `metadata: Mapping[str, Any]` — from Engine (filenames, etc.)
- `state: dict` — mutable run-scoped state
- `input_file_name: str | None`
- `logger: RunLogger | None`

Register with: `registry.register_row_detector(fn, row_kind="header"|"data"|..., priority=int)`

Return: `dict[str, float]` mapping row kind → score, or `None` / `{}`. Rules:
- Scores must be numeric, finite. Unknown keys are allowed for row detectors.
- A detector that cannot decide should return `{}` or `None`.

## Column detectors

Register with: `registry.register_column_detector(fn, field="<canonical_field>", priority=int)`

Context fields:
- `column_index: int`
- `header: Any`
- `values: Sequence[Any]` — full column
- `values_sample: Sequence[Any]` — first five values
- `sheet_name, metadata, state, input_file_name, logger`

Return: `dict[str, float]` keyed by **field name**, or `None` / `{}`. Rules:
- Keys **must** be registered fields (unknown fields raise `PipelineError`).
- Columns with no positive total score remain unmapped.

## Column transforms

Register with: `registry.register_column_transform(fn, field="<canonical_field>", priority=int)`

Context fields:
- `field_name: str`
- `values: Sequence[Any]` — starts as source column values; updated after each transform in the chain
- `mapping: Mapping[str, int]` — field → source column index
- `state, metadata, input_file_name, logger`

Return: `list[ColumnTransformResult]` where each item is `{"row_index": int, "value": dict|None}`. Rules:
- Must return a list exactly as long as the input column (`len(values)` when this transform runs).
- Every `row_index` must appear once; duplicates or missing indices raise `PipelineError`.
- You may emit additional keys inside `value` to create derived columns.

## Column validators

Register with: `registry.register_column_validator(fn, field="<canonical_field>", priority=int)`

Context fields:
- `field_name: str`
- `values: Sequence[Any]` — post-transform values for the field
- `mapping: Mapping[str, int]`
- `column_index: int`
- `state, metadata, input_file_name, logger`

Return: `list[ColumnValidatorResult]` where each item is `{"row_index": int, "message": str}`. Rules:
- List can be empty when no issues.
- `row_index` must be within the number of rows; messages must be non-empty strings.
- Validators **do not** stop the run; they only populate `table.issues` unless they raise.

## Hooks

Register with: `registry.register_hook(fn, hook_name=HookName.<...>, priority=int)`

Hook names: `on_workbook_start`, `on_sheet_start`, `on_table_detected`, `on_table_mapped`, `on_table_written`, `on_workbook_before_save`.

Context fields:
- `hook_name: HookName`
- `metadata: Mapping[str, Any]`
- `state: dict`
- `workbook: openpyxl.Workbook | None`
- `sheet: Worksheet | None`
- `table: TableData | None`
- `input_file_name: str | None`
- `logger: RunLogger | None`

Return: `None`. Raise to fail the run (wrapped as `HookError` with the stage name).

## Common guidance

- All callables should be **pure** with respect to inputs unless intentionally mutating `state`.
- Use `priority` to order competing detectors/validators/transforms; higher runs first.
- Keep signatures explicit (no reliance on the full context object).
- Use the provided `logger` for debug telemetry instead of `print`.

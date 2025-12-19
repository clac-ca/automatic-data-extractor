# Callable Contracts (v3)

This document defines the extension contracts for config packages. Config packages register callables imperatively with `registry.register_*` inside module-level `register(registry)` functions (auto-discovered and invoked by the engine).

Context objects are expanded into keyword arguments by `call_extension`, so authors declare only the parameters they need.

## Row detectors

Register with: `registry.register_row_detector(fn, row_kind="header"|"data"|..., priority=int)`

Context fields you can accept:

- `row_index: int` (1-based row number in the scanned sheet; Excel/openpyxl-style)
- `row_values: Sequence[Any]`
- `sheet_name: str`
- `settings` (engine settings)
- `metadata: Mapping[str, Any]`
- `state: dict`
- `input_file_name: str`
- `logger`

Return: `dict[str, float]` mapping row kind → score, or `None` / `{}`.

## Column detectors

Register with: `registry.register_column_detector(fn, field="<canonical_field>", priority=int)`

Context fields you can accept:

- `table: pl.DataFrame`
- `column: pl.Series`
- `column_sample: Sequence[str]` (trimmed, non-empty strings; size controlled by settings)
- `column_name: str`
- `column_index: int`
- `header_text: str` (trimmed; `""` if missing)
- `table_region: TableRegion`
- `table_index: int`
- `settings` (engine settings)
- `sheet_name: str`
- `metadata: Mapping[str, Any]`
- `state: dict`
- `input_file_name: str`
- `logger`

Return: `dict[str, float]` keyed by field name, or `None` / `{}`.

## TableRegion

`TableRegion` is a simple bounding box in worksheet coordinates (1-based, inclusive):

- `min_row`, `min_col`, `max_row`, `max_col`
- `a1`: `"B5:G20"`-style range string
- Convention: `min_row` is the header row (`table_region.header_row`).

## Transforms (v3)

Transforms operate on the table DataFrame and return Polars expressions.

Register with: `registry.register_column_transform(fn, field="<canonical_field>", priority=int)`

Recommended signature:

```py
def transform(
    *,
    field_name: str,
    table: pl.DataFrame,
    table_region: TableRegion,
    table_index: int,
    input_file_name: str,
    settings,
    state: dict,
    metadata: dict,
    logger,
    **_,
) -> pl.Expr | None:
    ...
```

Return types:

- `None`: no change
- `pl.Expr`: replacement expression for `field_name`

The engine applies outputs via `table.with_columns(...)` and must not change row count.
For derived columns or multi-column edits, use a table hook (e.g., `on_table_mapped` or `on_table_transformed`).

## Validators (v3 inline)

Validators return an expression that evaluates to either null (valid) or a message (invalid).

Register with: `registry.register_column_validator(fn, field="<canonical_field>", priority=int)`

Recommended signature:

```py
def validate(
    *,
    field_name: str,
    table: pl.DataFrame,
    table_region: TableRegion,
    table_index: int,
    input_file_name: str,
    settings,
    state: dict,
    metadata: dict,
    logger,
    **_,
) -> pl.Expr | None:
    ...
```

Where issues go:

- For each validated field `field_name`, the engine writes `__ade_issue__{field_name}` (Utf8 | Null).
- The engine also writes summary columns:
  - `__ade_has_issues` (Boolean)
  - `__ade_issue_count` (Int32)

## Reserved columns

The engine reserves the prefix `__ade_` for internal/diagnostic columns.

- Config packages should not register canonical fields starting with `__ade_`.
- Reserved columns are dropped from output by default (see settings).

## Hooks

Register with: `registry.register_hook(fn, hook="<hook_stage>", priority=int)`

Table hooks that may replace the DataFrame:

- `on_table_mapped`
- `on_table_transformed`
- `on_table_validated`

These hooks may return `pl.DataFrame` or `None`. All other hooks must return `None`.

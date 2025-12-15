# Callable Contracts (v2)

This is the authoritative contract for every extension callable. Config packages register callables imperatively with `registry.register_*` inside their `register(registry)` entrypoint. Context objects are expanded into keyword arguments by `call_extension`, so authors declare only the parameters they need.

This document uses **MUST/SHOULD/MAY** normatively.

## Purpose (Transforms + Validators)

Normalize a detected table (header + data rows) into a canonical table of registered fields, optionally producing derived canonical fields, and emitting validation issues in a shape that mirrors transforms.

## Definitions (Transforms + Validators)

### Canonical field

A field is a canonical output column declared via `registry.register_field(FieldDef(name=...))`.

Transforms and validators **MUST NOT** emit unknown fields.

### Row count `N`

`N` is the number of data rows in the detected table region (excludes the header row).

All column vectors passed to and returned from transforms/validators have length **exactly `N`**.

### Column vector

```py
ColumnVec = list[Any]  # length N
```

### TableView

A read-only view of the current canonical table state:

- `table.row_count -> int` (== `N`)
- `table.get(field: str) -> ColumnVec | None`
- `table.fields() -> list[str]` (fields currently present)
- `table.mapping.get(field: str) -> int | None` (source column index if mapped; `None` if derived)

`TableView` MUST NOT allow mutation of the engine’s underlying vectors.

### Mapping

```py
mapping: dict[str, int | None]  # canonical field -> source column index (or None if derived)
```

## Row detectors

Context fields you can accept:
- `row_index: int`
- `row_values: Sequence[Any]` — values for that row (trimmed)
- `sheet_name: str`
- `metadata: Mapping[str, Any]` — from Engine (filenames, etc.)
- `state: dict` — mutable run-scoped state
- `input_file_name: str | None`
- `logger: RunLogger` (may be `NullLogger` in tests)

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
- `field_name: str` — the field this transform is registered under
- `column: ColumnVec` — current vector for `field_name`
- `table: TableView` — read-only canonical table view (for cross-field inspection)
- `mapping: dict[str, int | None]`
- `state, metadata, input_file_name, logger`

Invocation order (deterministic):

- **Phase 1 (mapped fields):** for each mapped field in source column order, run its transform chain ordered by:
  1. priority desc
  2. module asc
  3. qualname asc
- **Phase 2 (derived-only fields):** after phase 1 completes, for each non-mapped field currently present in the table that has transforms registered, run its transform chain using the same ordering.

Return types:

- `None` → no change
- `ColumnVec` → replaces the owner field (`field_name`)
- `dict[str, ColumnVec]` → values patch (may include derived fields)
- `{"values": dict[str, ColumnVec], "issues": dict[str, list[IssueCell]]|None, "meta": dict|None}` → table patch envelope (future-proof)

Constraints (MUST):

- All returned keys MUST be registered fields (unknown field → `PipelineError`).
- Every returned vector MUST have length `N` (wrong length → `PipelineError`).
- Transforms MUST NOT change row count.

## Column validators

Register with: `registry.register_column_validator(fn, field="<canonical_field>", priority=int)`

Context fields:
- `field_name: str` — the field this validator is registered under
- `column: ColumnVec` — post-transform values for `field_name`
- `table: TableView`
- `mapping: dict[str, int | None]`
- `state, metadata, input_file_name, logger`

Validators run after all transforms complete (including phase 2 derived transforms), using the same phasing and deterministic ordering as transforms.

Issue types:

```py
Issue = {
  "message": str,  # REQUIRED, non-empty
  "severity": "info"|"warning"|"error" | None,  # optional
  "code": str | None,  # optional
  "meta": dict[str, Any] | None,  # optional
}

IssueCell = None | Issue | list[Issue]
```

Return types:

- `None` / `[]` → no issues
- `list[{"row_index": int, "message": str, ...}]` → sparse issues list (optional: `field`, `severity`, `code`, `meta`)
- `dict[str, list[IssueCell]]` → issue patch vectors (each list length `N`)
- `{"issues": dict[str, list[IssueCell]], "meta": dict|None}` → table patch envelope

Constraints (MUST):

- Emitted issue keys MUST be registered fields (unknown field → `PipelineError`).
- Issue vectors MUST have length `N` (wrong length → `PipelineError`).
- Sparse issues MUST have `row_index` in `[0, N)` and a non-empty `message`.
- Validators MUST NOT mutate table values. If a validator returns `"values"` in a table patch envelope, the engine raises `PipelineError`.

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
- `logger: RunLogger` (may be `NullLogger` in tests)

Return: `None`. Raise to fail the run (wrapped as `HookError` with the stage name).

## Common guidance

- All callables should be **pure** with respect to inputs unless intentionally mutating `state`.
- Use `priority` to order competing detectors/validators/transforms; higher runs first.
- Keep signatures explicit (no reliance on the full context object).
- Use the provided `logger` for debug telemetry instead of `print`.

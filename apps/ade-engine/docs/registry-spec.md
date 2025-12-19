# Registry Specification

The Registry is the in-memory catalogue of everything a config package provides. Config packages populate it imperatively via `registry.register_*` calls inside module-level `register(registry)` functions that the engine auto-discovers and invokes, then the engine finalizes it before the pipeline runs.

## Stored objects

- **Fields** (`FieldDef`) — canonical schema the config package targets. Fields may carry `label`, `dtype`, and arbitrary `meta`.
- **Row detectors** — callable plus metadata (`row_kind`, `priority`).
- **Column detectors** — callable + `field` + `priority`.
- **Column transforms** — callable + `field` + `priority`.
- **Column validators** — callable + `field` + `priority`.
- **Hooks** — callable + hook stage + `priority` for workbook/sheet/table lifecycle.

`RegisteredFn` keeps `fn`, `priority`, `module`, `qualname`, and the relevant field/row_kind/hook stage (internal key).

## Ordering

`Registry.finalize()` sorts every list by:
1. Priority (descending; higher number runs first)
2. Module name (ascending)
3. Qualname (ascending)

Transforms/validators are additionally grouped by field (`column_transforms_by_field`, `column_validators_by_field`) for efficient lookup.

## Field handling

- `register_field(FieldDef)` adds a new field; duplicates raise an error.

## Score validation

Detectors must return score patches (dict[str, float] or `None`). `validate_detector_scores` enforces:
- Numeric, finite scores.
- All keys must be known fields for column detectors. Row detectors may emit unknown keys when `allow_unknown=True`.
- Raises `PipelineError` on invalid payloads.

## Hooks

Hook lists are stored under internal `HookName` enum keys, but config packages register by string stage name:
- `on_workbook_start`, `on_sheet_start`, `on_table_mapped`, `on_table_transformed`, `on_table_validated`, `on_table_written`, `on_workbook_before_save`

Hook failures raise `HookError` with the stage name; the run is marked failed.

## Invocation semantics

`call_extension` maps dataclass context fields onto the callable’s signature:
- Only parameters present in the context are passed.
- Missing required parameters cause a `PipelineError`.
- `*args` / `**kwargs` are tolerated but not required.
- Any exception from the callable is wrapped as `PipelineError` (or `HookError` for hooks) so the run can attribute the failure.

There is no decorator-based discovery. Config packages are responsible for calling `registry.register_*` explicitly inside module-level `register(registry)` functions.

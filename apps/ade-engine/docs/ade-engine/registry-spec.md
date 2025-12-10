# Registry Spec (Fields, Detectors, Transforms, Validators, Hooks)

**Core types**
- `FieldDef(name, label, required, dtype, synonyms, meta)`
- `HookName` enum: workbook/table lifecycle hooks.
- Contexts: RowDetectorContext, ColumnDetectorContext, TransformContext, ValidateContext, HookContext.

**Ordering**
- Sorting key `(priority desc, module asc, qualname asc)` applied in `Registry.finalize()`.

**ScorePatch normalization**
- Accepts float/int or dict[str,float]; drops NaN/unknown fields unless `allow_unknown=True`.

**Registration decorators**
- `@field_meta`, `@row_detector(row_kind, priority)`, `@column_detector(field, priority)`, `@column_transform(field, priority)`, `@column_validator(field, priority)`, `@hook(HookName, priority)`.
- Duplicate fields raise `ValueError`.

**Validation rules**
- Unknown field keys in patches ignored; normalize scores to floats.

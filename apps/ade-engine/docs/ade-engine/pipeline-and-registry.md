# Pipeline + Registry Flow

1) Load `Settings`.
2) Build `Registry`; `set_current_registry` then `import_all(config_package)`; `finalize()` to sort.
3) Extract workbook via openpyxl helpers.
4) **Row detection**: run `registry.row_detectors` per row → pick header row.
5) **Column detection/mapping**: run `registry.column_detectors` per column → scores → mapping with tie policy.
6) **Hook** `ON_TABLE_MAPPED` can reorder/patch columns.
7) **Transform**: run `registry.column_transforms` per mapped field; merge row dicts.
8) **Validate**: run `registry.column_validators`; record issues only.
9) **Render**: mapped columns keep input order; unmapped appended if enabled.
10) **Hook** `ON_TABLE_WRITTEN` / `ON_WORKBOOK_BEFORE_SAVE` before save.

Shared `state` dict flows through all contexts; run_metadata holds input/output identifiers.

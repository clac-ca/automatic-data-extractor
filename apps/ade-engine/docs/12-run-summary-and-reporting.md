# Run Summary and Reporting (`ade.summary`)

The engine now owns the **authoritative hierarchical summaries** for runs. During
each pipeline execution it builds table, sheet, file, and run summaries and
emits them as telemetry events. Downstream services (e.g., `ade-api`) should
persist the `engine.run.summary` payload instead of recomputing from the event
log.

## 1. Inputs and outputs

- Inputs:
  - Normalized tables (`NormalizedTable` objects) produced during the run.
  - Optional: `manifest.json` for field labels/required flags.
  - Run context metadata (workspace/config/run IDs, engine/config versions, environment reuse markers).
- Outputs:
  - `TableSummary`, `SheetSummary`, `FileSummary`, `RunSummary` models (see `schemas/summaries.py`).
  - Events: `engine.table.summary` (per table), `engine.sheet.summary` / `engine.file.summary` (aggregates), and `engine.run.summary` (final).

## 2. Schema highlights

All summaries share the same shape (`BaseSummary`):

- `schema_id` / `schema_version` — defaults to `ade.summary` / `1.0.0`.
- `scope` — `"table" | "sheet" | "file" | "run"`.
- `id` and `parent_ids` — simple identifiers (e.g., `"tbl_0"`, `"file_0"`) plus references to parents.
- `source` — scope-specific metadata (run/file/sheet ids, versions, timestamps, failure info, etc.).
- `counts` — `rows`, `columns`, `fields`, plus optional `files`/`sheets`/`tables` totals.
  - Rows: `total`, `empty`, `non_empty`.
  - Columns: physical totals + distinct header counts (mapped vs unmapped).
  - Fields: canonical/required counts + mapped/unmapped breakdowns.
- `fields` — table uses `FieldSummaryTable` (mapped column, score, header); aggregate scopes use `FieldSummaryAggregate` (mapped flag + counts of tables/sheets/files mapped).
- `columns` — table uses `ColumnSummaryTable` (physical column, emptiness, mapped field/score/output_header); aggregate scopes use `ColumnSummaryDistinct` (normalized header, occurrences, mapped fields).
- `validation` — `rows_evaluated`, `issues_total`, `issues_by_severity/code/field`, `max_severity`.
- `details` — free-form scope metadata (table ids, sheet ids, output paths, processed files, etc.).

Percentages are intentionally omitted; derive them from counts in BI/analytics.

## 3. Aggregation in the engine

`SummaryAggregator` (`core/pipeline/summary_builder.py`) builds summaries from the
in-memory pipeline artifacts:

1. Capture run identity/version metadata from `RunContext`.
2. For each normalized table, build a `TableSummary`, emit `engine.table.summary`, and update aggregate state.
3. After tables finish, finalize sheet/file/run aggregates and emit `engine.sheet.summary`, `engine.file.summary`, and `engine.run.summary`, then emit `engine.complete`.

## 4. Guidance for consumers

- Treat `events.ndjson` as the **source of truth**; persist `engine.run.summary`
  to a DB column for API/UI access.
- Use sheet/file summaries for drill-down analytics; leverage distinct headers,
  mapped/unmapped field counts, and validation tallies for reporting.
- When adding new mapping/validation dimensions, extend the summary models first
  (counts/fields/columns/validation) and keep percentages in downstream tools.

## 5. Example `engine.run.summary` (abridged)

```json
{
  "schema_id": "ade.summary",
  "schema_version": "1.0.0",
  "scope": "run",
  "id": "run",
  "parent_ids": { "run_id": "c5..." },
    "source": {
        "run_id": "c5...",
        "workspace_id": "c1...",
        "configuration_id": "c2...",
        "engine_version": "1.6.1",
        "config_version": "0.1.0",
        "started_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:00:03Z",
        "status": "succeeded"
  },
  "counts": {
    "files": { "total": 1 },
    "sheets": { "total": 1 },
    "tables": { "total": 2 },
    "rows": { "total": 15, "empty": 1, "non_empty": 14 },
    "columns": { "physical_total": 6, "physical_empty": 0, "physical_non_empty": 6, "distinct_headers": 6, "distinct_headers_mapped": 4, "distinct_headers_unmapped": 2 },
    "fields": { "total": 5, "required": 3, "mapped": 4, "unmapped": 1, "required_mapped": 3, "required_unmapped": 0 }
  },
  "fields": [
    { "field": "member_id", "label": "Member ID", "required": true, "mapped": true, "max_score": 0.98, "tables_mapped": 2, "sheets_mapped": 1, "files_mapped": 1 }
  ],
  "columns": [
    { "header": "member_id", "header_normalized": "member_id", "occurrences": { "tables_seen": 2, "physical_columns_seen": 2, "physical_columns_non_empty": 2, "physical_columns_mapped": 2 }, "mapped": true, "mapped_fields": ["member_id"], "mapped_fields_counts": { "member_id": 2 } }
  ],
  "validation": {
    "rows_evaluated": 15,
    "issues_total": 3,
    "issues_by_severity": { "error": 2, "warning": 1 },
    "issues_by_code": { "missing": 1, "invalid": 1, "empty": 1 },
    "issues_by_field": { "email": 2 }
  },
  "details": {
    "file_ids": ["file_0"],
    "sheet_ids": ["sheet_0"],
    "table_ids": ["tbl_0", "tbl_1"],
    "processed_file": "input.xlsx",
    "output_path": "output/normalized.xlsx"
  }
}
```

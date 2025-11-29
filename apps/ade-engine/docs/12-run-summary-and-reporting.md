# Run Summary and Reporting (`ade.run_summary/v1`)

The engine now emits **telemetry events only**. Run summaries are **projections**
built by downstream services (e.g., `ade-api`) from the event log and, if
needed, the normalized outputs. This document explains the `RunSummaryV1`
schema and how to derive it from events.

## 1. Inputs and outputs

- Input: `events.ndjson` written by the engine (events use `ade.event/v1`).
- Optional input: `manifest.json` for label/required metadata.
- Optional input: normalized workbook(s) for row counts when events are missing counts.
- Output: `RunSummaryV1` (Pydantic model in `ade_engine.schemas.run_summary`).

The engine does **not** write `run_summary.json` or `artifact.json`.

## 2. Schema overview

`RunSummaryV1` fields (see `schemas/run_summary.py` for the authoritative model):

- `run` — identity and lifecycle (id, workspace/config ids, status, failure details, engine/config versions, timestamps).
- `core` — top-level metrics (input file/sheet counts, table count, row count, mapped/required/canonical field counts, unmapped column count, validation issue tallies).
- `breakdowns.by_file` — per-source-file table counts, row counts, issue breakdowns.
- `breakdowns.by_field` — per-field mapping/score/validation breakdowns.

## 3. Building a summary from events

Event types used:

- `run.started` — provides start timestamp and engine version (optional).
- `run.table.summary` — provides per-table row counts, mapped field scores, unmapped column counts, and validation breakdowns.
- `run.completed` — provides completion timestamp, status, and structured error payload.

Algorithm outline:

1. Parse all events for the run into memory (ordering by `created_at` when available).
2. Capture `started_at`/`engine_version` from the first `run.started` event.
3. For each `run.table.summary` event, extract:
   - `source_file`, `source_sheet`, `table_index`
   - `row_count`
   - `mapped_fields` (field + score + required/satisfied flags)
   - `unmapped_column_count`
   - `validation` (totals, by severity/code/field)
4. Aggregate counts:
   - File-level: table count, row count (only if every table for a file reported a row_count), issue counts.
   - Field-level: mapped flag, max score, issue counts by severity/code.
   - Core metrics: totals across files/fields, unmapped column total, canonical/required field counts (from manifest when provided).
5. Capture completion status/error/timestamps from the last `run.completed` event.
6. Compute `duration_seconds` when both start and completion timestamps are present.

If some tables omit `row_count`, propagate `row_count: null` in core and by-file
breakdowns to avoid guessing.

## 4. Guidelines for consumers

- Treat `events.ndjson` as the **source of truth**. Do not expect artifact files.
- Store summaries in your service (DB column or JSON file) so UIs can fetch a lightweight projection.
- Version independently: `RunSummaryV1` is owned by `ade-engine` but evolves separately from events. If you add new fields to `run.table.summary` events, update the summary builder and bump the summary version.
- When adding new validation/mapping dimensions, extend the `run.table.summary` payload first; then update the builder to aggregate it.

## 5. Example `run.table.summary` event payload (engine-emitted)

```json
{
  "type": "run.table.summary",
  "created_at": "2024-01-01T00:00:02Z",
  "run_id": "run_123",
  "payload": {
    "table_id": "tbl_0",
    "source_file": "input.xlsx",
    "source_sheet": "Sheet1",
    "table_index": 0,
    "row_count": 10,
    "column_count": 5,
    "mapped_fields": [
      {"field": "member_id", "score": 1.0, "is_required": true, "is_satisfied": true}
    ],
    "mapping": {
      "mapped_columns": [
        {"field": "member_id", "header": "Member ID", "source_column_index": 0, "score": 1.0, "is_required": true, "is_satisfied": true}
      ],
      "unmapped_columns": [
        {"header": "Extra", "source_column_index": 4, "output_header": "raw_1"}
      ]
    },
    "unmapped_column_count": 1,
    "validation": {
      "total": 3,
      "by_severity": {"error": 2, "warning": 1},
      "by_code": {"missing": 1, "invalid": 1, "empty": 1},
      "by_field": {
        "email": {"total": 2, "by_severity": {"error": 2}, "by_code": {"missing": 1, "invalid": 1}}
      }
    },
    "details": {
      "header_row": 1,
      "first_data_row": 2,
      "last_data_row": 11
    }
  }
}
```

## 6. Example `RunSummaryV1` (abridged)

```json
{
  "schema": "ade.run_summary/v1",
  "version": "1.0.0",
  "run": {
    "id": "run_123",
    "status": "succeeded",
    "engine_version": "0.2.0",
    "started_at": "2024-01-01T00:00:00Z",
    "completed_at": "2024-01-01T00:00:03Z",
    "duration_seconds": 3.0
  },
  "core": {
    "input_file_count": 1,
    "input_sheet_count": 1,
    "table_count": 2,
    "row_count": 15,
    "canonical_field_count": 3,
    "required_field_count": 2,
    "mapped_field_count": 2,
    "unmapped_column_count": 1,
    "validation_issue_count_total": 3,
    "issue_counts_by_severity": {"error": 2, "warning": 1},
    "issue_counts_by_code": {"missing": 1, "invalid": 1, "empty": 1}
  },
  "breakdowns": {
    "by_file": [
      {
        "source_file": "input.xlsx",
        "table_count": 2,
        "row_count": 15,
        "validation_issue_count_total": 3,
        "issue_counts_by_severity": {"error": 2, "warning": 1},
        "issue_counts_by_code": {"missing": 1, "invalid": 1, "empty": 1}
      }
    ],
    "by_field": [
      {"field": "member_id", "label": "Member ID", "required": true, "mapped": true, "max_score": 1.0, "validation_issue_count_total": 0},
      {"field": "email", "label": "Email", "required": true, "mapped": true, "max_score": 0.82, "validation_issue_count_total": 2}
    ]
  }
}
```

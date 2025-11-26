# 12 – Run summary and reporting

This document defines the **run summary** object:

- the JSON structure used in `run.completed` events,
- the metrics we persist in the `runs` table,
- and how it is computed from `artifact.json` and `events.ndjson`.

The goal is to have a **simple, well-thought-through shape** that:

- powers front-end run detail views,
- can be exported over the last N days for BI (e.g. Power BI),
- and stays stable as the engine evolves.

---

## 1. Design goals

1. **Small but complete**

   - Compact enough to embed in events and a single DB row.
   - Rich enough that most reporting doesn’t need to re-scan artifacts.

2. **Two tiers**

   - **Core**: flat metrics suitable for real DB columns.
   - **Breakdowns**: per-file / per-field metrics stored as nested JSON and
     optionally exploded into dimension tables.

3. **Derived from artifacts**

   - Calculated by the ADE API at the end of a run.
   - Uses `artifact.json` as source of truth; optionally `events.ndjson` for
     timing or phase data.

4. **Versioned**

   - Schema tagged as `"ade.run_summary/v1"`.
   - Additive changes only within v1; breaking changes require v2.

---

## 2. High-level shape

```jsonc
{
  "schema": "ade.run_summary/v1",
  "version": "1.0.0",

  "run": { ...identity and lifecycle... },

  "core": { ...flat metrics for BI columns... },

  "breakdowns": {
    "by_file": [ ... ],
    "by_field": [ ... ]
  }
}
```

* `run` – identity, modes, and timing that you might also store in columns.
* `core` – a small, flat set of metrics you definitely store as columns.
* `breakdowns` – more detailed slices, stored as JSON and/or exploded into
  auxiliary tables.

---

## 3. `run` block – identity & lifecycle

```jsonc
"run": {
  "run_id": "run_2025_11_26_001",
  "workspace_id": "ws_42",
  "configuration_id": "cfg_members_v3",
  "configuration_name": "Members v3 – Production",

  "mode": "production",        // production | test | validation
  "status": "succeeded",       // succeeded | failed | canceled

  "env_reason": "reuse_ok",    // reuse_ok | force_rebuild | missing_env | digest_mismatch | engine_spec_mismatch | python_mismatch

  "engine_version": "0.2.0",
  "config_version": "3.1.0",

  "started_at": "2025-11-26T12:00:00Z",
  "completed_at": "2025-11-26T12:00:09Z",
  "duration_ms": 9000
}
```

Recommended DB columns:

* `run_id`, `workspace_id`, `configuration_id`,
* `mode`, `status`, `env_reason`,
* `engine_version`, `config_version`,
* `started_at`, `completed_at`, `duration_ms`.

These fields overlap with the `run` block in `run.completed` events; keeping
them identical makes life easier for both FE and BI.

---

## 4. `core` block – flat metrics for BI

These metrics should be **queryable as normal columns** in the `runs` table:

```jsonc
"core": {
  "total_files": 1,
  "total_sheets": 2,
  "total_tables": 2,
  "total_rows": 1230,

  "error_count": 8,
  "warning_count": 21,
  "issue_counts_by_severity": {
    "error": 8,
    "warning": 21
  },
  "issue_counts_by_code": {
    "missing_required": 5,
    "invalid_format": 3,
    "future_date": 4,
    "out_of_range": 2,
    "unknown_value": 15
  },

  "rows_with_issues": 30,
  "issue_rate_per_1k_rows": 23.6,

  "declared_fields": 12,   // from manifest.columns.fields
  "mapped_fields": 11,     // fields with ≥ 1 mapped column across tables
  "unmapped_fields": 1,

  "avg_mapping_score": 0.93,
  "min_mapping_score": 0.78
}
```

### 4.1 Field semantics

* `total_files`  
  Count of distinct `source_file` values in `artifact.tables`.

* `total_sheets`  
  Count of distinct `(source_file, source_sheet)` pairs.

* `total_tables`  
  `len(artifact.tables)`.

* `total_rows`  
  Sum of per-table row counts; derive from `NormalizedTable.rows` length or
  row index ranges recorded in the artifact.

* `error_count`, `warning_count`  
  Count of `validation_issues` by severity (`error` / `warning`).

* `issue_counts_by_severity`  
  Aggregated counts for each severity level (extensible).

* `issue_counts_by_code`  
  Map from validation `code` to count. Adapts to new error codes without schema
  changes.

* `rows_with_issues`  
  Count of distinct `(source_file, source_sheet, row_index)` with ≥1 issue.

* `issue_rate_per_1k_rows`  
  `(error_count + warning_count) / max(total_rows, 1) * 1000`.

* `declared_fields`  
  `len(manifest.columns.fields)`.

* `mapped_fields`  
  Canonical fields with ≥1 `mapped_columns` entry across tables.

* `unmapped_fields`  
  `declared_fields - mapped_fields`.

* `avg_mapping_score`  
  Average of all `mapped_columns[].score` values across tables.

* `min_mapping_score`  
  Minimum of all `mapped_columns[].score` values across tables; `null` if none.

### 4.2 Recommended DB columns

At minimum:

* `total_files`, `total_sheets`, `total_tables`, `total_rows`,
* `error_count`, `warning_count`, `rows_with_issues`,
* `issue_rate_per_1k_rows`,
* `declared_fields`, `mapped_fields`, `unmapped_fields`,
* `avg_mapping_score`, `min_mapping_score`.

JSON columns (optional):

* `issue_counts_by_severity`, `issue_counts_by_code`.

---

## 5. `breakdowns` – detailed slices

### 5.1 `breakdowns.by_file` – per-file metrics

Example:

```jsonc
"breakdowns": {
  "by_file": [
    {
      "source_file": "members.xlsx",

      "sheet_count": 2,
      "table_count": 2,
      "row_count": 1230,

      "issue_counts_by_severity": {
        "error": 8,
        "warning": 21
      },
      "issue_counts_by_code": {
        "missing_required": 5,
        "invalid_format": 3,
        "future_date": 4,
        "out_of_range": 2,
        "unknown_value": 15
      },

      "mapped_fields": 11,
      "unmapped_fields": 1
    }
  ],
```

Derived as:

* group `artifact.tables` by `source_file`,
* aggregate per group:

  * `sheet_count` = distinct `source_sheet`,
  * `table_count` = number of tables,
  * `row_count` = sum of rows,
  * `issue_*` and `mapped/unmapped_fields` = same logic as `core`, scoped to
    that file.

Use cases:

* FE: “per file” cards on a run detail page.
* BI: optional `run_files` dimension table (`run_id`, `source_file`, metrics).

### 5.2 `breakdowns.by_field` – per-field quality

Example:

```jsonc
    "by_field": [
      {
        "field": "member_id",

        "mapped_table_count": 2,
        "mapped_column_count": 2,

        "avg_mapping_score": 0.99,
        "min_mapping_score": 0.97,

        "issue_counts_by_severity": {
          "error": 0,
          "warning": 0
        },
        "issue_counts_by_code": {},
        "rows_with_issues": 0,
        "issue_rate_per_1k_rows": 0.0
      },
      {
        "field": "email",

        "mapped_table_count": 2,
        "mapped_column_count": 2,

        "avg_mapping_score": 0.94,
        "min_mapping_score": 0.88,

        "issue_counts_by_severity": {
          "error": 3,
          "warning": 4
        },
        "issue_counts_by_code": {
          "invalid_format": 3,
          "unknown_value": 4
        },
        "rows_with_issues": 7,
        "issue_rate_per_1k_rows": 5.7
      }
    ]
  }
}
```

Field semantics:

* `field`  
  Canonical field ID from the manifest.

* `mapped_table_count`  
  Number of tables where this field appears in `mapped_columns`.

* `mapped_column_count`  
  Total count of mapped physical columns for this field across all tables.

* `avg_mapping_score`, `min_mapping_score`  
  As for `core`, but restricted to this field.

* `issue_counts_by_severity`, `issue_counts_by_code`  
  Aggregated from `validation_issues` where `field` matches.

* `rows_with_issues`  
  Distinct rows where this field had at least one issue.

* `issue_rate_per_1k_rows`  
  `(issues_for_field / max(total_rows, 1)) * 1000`.

Use cases:

* FE: per-field quality summary (“email is your worst field this run”).
* BI: `run_field_metrics` table for “Top problem fields per config” dashboards.

---

## 6. JSON in events and in the `runs` table

### 6.1 In `run.completed` events

The run summary is embedded inside the `run` payload of `run.completed` events:

```jsonc
{
  "type": "run.completed",
  "run_id": "run_2025_11_26_001",
  "run": {
    "status": "succeeded",
    "mode": "production",
    "execution_summary": {
      "exit_code": 0,
      "duration_ms": 9000
    },
    "artifact_path": "logs/artifact.json",
    "events_path": "logs/events.ndjson",
    "output_paths": ["output/normalized.xlsx"],

    "summary": {
      "schema": "ade.run_summary/v1",
      "version": "1.0.0",
      "run": { ... },
      "core": { ... },
      "breakdowns": { ... }
    }
  }
}
```

Front-ends can:

* listen for `run.completed`,
* read `run.summary`,
* render cards and charts without hitting the DB.

### 6.2 In the `runs` table

When a `run.completed` event arrives, the API should:

1. **Flatten `run` and `core`**  
   into columns on `runs` (identity + metrics).

2. **Store the full summary JSON**  
   in a JSON column on `runs` (e.g. `summary_json`), or  
   in a separate `run_summaries` table keyed by `run_id`.

Conceptual schema:

```text
runs
  run_id (PK)
  workspace_id
  configuration_id
  mode
  status
  env_reason
  engine_version
  config_version
  started_at
  completed_at
  duration_ms
  total_files
  total_sheets
  total_tables
  total_rows
  error_count
  warning_count
  rows_with_issues
  issue_rate_per_1k_rows
  declared_fields
  mapped_fields
  unmapped_fields
  avg_mapping_score
  min_mapping_score
  summary_json (JSON)
```

Optional exploded table:

```text
run_field_metrics
  run_id (FK → runs)
  field
  mapped_table_count
  mapped_column_count
  rows_with_issues
  issue_rate_per_1k_rows
  error_count
  warning_count
```

With these two tables you can drive most dashboards.

---

## 7. Implementation sketch

The summarization code runs in the API after the engine finishes:

1. **Load artifacts**  
   * parse `artifact.json`,  
   * optionally parse `events.ndjson` for timing if needed.

2. **Aggregate core metrics**  
   * iterate `artifact.tables` to compute row counts, mapped field scores, and
     validation issue stats (by severity, by code, by field, by file).

3. **Compute derived fields**  
   * apply formulas for rates, declared vs mapped fields, mapping scores, etc.

4. **Assemble the summary object**  
   * fill `run`, `core`, `breakdowns.by_file`, `breakdowns.by_field`.

5. **Attach and persist**  
   * embed in the final `run.completed` event,  
   * write columns + summary JSON into `runs` (and optionally
     `run_field_metrics`).

The engine **does not** compute summaries; it only guarantees that
`artifact.json` and `events.ndjson` contain the data needed to derive them.

---

## 8. Versioning

Run summaries are versioned via:

* `schema = "ade.run_summary/v1"`,
* `version = "1.0.0"`.

Within v1:

* Add optional fields only.
* Do not rename or remove existing fields.

Breaking changes (e.g., reworking `breakdowns`) should:

* introduce `"ade.run_summary/v2"`,
* accompany a migration plan for DB columns and consumers.

Start with the v1 fields above; they cover most reporting needs while leaving
room to extend.

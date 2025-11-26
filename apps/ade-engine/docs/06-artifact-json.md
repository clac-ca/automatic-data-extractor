# Artifact JSON (`artifact.json`)

`artifact.json` is the **per-run audit record** produced by the engine.

It answers:

> “Exactly what did the engine do to this set of spreadsheets, and why?”

Everything else (UI, summaries, reports, AI, etc.) should treat
`artifact.json` as the **source of truth for run-level details**. The ADE API
derives **run summaries** and **event streams** from this file plus
`events.ndjson`.

This document defines:

- File location and lifecycle.
- The **schema for artifact v1**.
- How tables, mappings, and validation are represented.
- The invariants consumers can rely on.
- How ADE API is expected to consume it and relate it to run summaries.

## Terminology

| Concept        | Term in code        | Notes                                                     |
| -------------- | ------------------- | --------------------------------------------------------- |
| Run            | `run`               | One call to `Engine.run()` or one CLI invocation         |
| Config package | `config_package`    | Installed `ade_config` package for this run              |
| Config version | `manifest.version`  | Version declared by the config package manifest          |
| Build          | build               | Virtual environment built for a specific config version  |
| User data file | `source_file`       | Original spreadsheet on disk                             |
| User sheet     | `source_sheet`      | Worksheet/tab in the spreadsheet                         |
| Canonical col  | `field`             | Defined in manifest; never call this a “column”          |
| Physical col   | column              | B / C / index 0,1,2… in a sheet                          |
| Output workbook| normalized workbook | Written to `output_dir`; includes mapped + normalized data |

Artifact docs stick to these terms; telemetry and run summaries reuse the same
vocabulary.

---

## 1. File location & lifecycle

### 1.1 Where it lives

For each **engine run** there is exactly **one** artifact file:

- Path: `RunPaths.artifact_path`
- Convention: `<logs_dir>/artifact.json`

Where `<logs_dir>` is:

- passed in via `RunRequest.logs_dir`, or
- inferred by the engine from the input location (see runtime docs).

### 1.2 When it’s created and updated

`FileArtifactSink` in `infra/artifact.py` manages the lifecycle:

1. **Start of run**

   - Creates an in-memory artifact structure:

     - `run.status = "running"`,
     - `run.id`, `run.started_at`,
     - `config` metadata (`schema`, `version`, `name`),
     - empty `tables` and `notes`.

2. **During the run**

   - Each pipeline stage calls into the sink:

     - `record_table(...)` to append table summaries (mapping + validation).
     - `note(...)` to append high-level notes.

   - This may happen multiple times (e.g., one `record_table` per table).

3. **On completion (success or failure)**

   - `mark_success(outputs=...)` or `mark_failure(error=...)`:

     - sets `run.status`,
     - sets `run.completed_at`,
     - writes either `outputs` or `error`.

   - `flush()` writes JSON to disk **atomically**:

     - serialize to `artifact.json.tmp`,
     - `fsync`,
     - rename to `artifact.json`.

### 1.3 Guarantees

For **every** engine run (even failed ones):

- `artifact.json` exists at `RunPaths.artifact_path`.
- It is well-formed JSON.
- `run.status` is either `"succeeded"` or `"failed"`.

Run summaries and reporting code can rely on this: if a run exists, it has an
artifact.

---

## 2. Design goals

The artifact schema is intentionally:

- **Human-inspectable**  
  Easy to read in an editor or pretty-printed for debugging.

- **Stable & versioned**  
  Changes are additive where possible; breaking changes bump the version.

- **Downstream friendly**  
  ADE API, reporting, and AI agents can:

  - reconstruct mapping decisions,
  - count validation issues by field / code / severity,
  - see how many tables were processed and from which files/sheets.

- **Backend-run-agnostic**  
  No first-class notion of “run request” or “workspace”; those live in the API.
  Engine treats any IDs passed in via `RunRequest.metadata` as opaque tags, not
  first-class fields.

- **Deliberately minimal**  
  Artifact is the durable, human-oriented audit log:

  - run-level info,
  - compact mapping summaries (with per-column contributions),
  - compact validation summaries,
  - high-level notes.

  **Per-row detail** and “live timeline” are expressed via telemetry in
  `events.ndjson`, and **aggregate metrics** for reporting are expressed via
  run summaries (see `12-run-summary-and-reporting.md`).

---

## 3. Top-level schema (v1)

Artifact JSON v1 has this high-level shape:

```jsonc
{
  "schema": "ade.artifact/v1",
  "version": "1.0.0",

  "run": { ... },
  "config": { ... },
  "tables": [ ... ],
  "notes": [ ... ]
}
```

### 3.1 Conventions

Across the schema:

* Timestamps are **ISO 8601** strings in UTC (`"2024-01-01T12:00:00Z"`).
* File paths in `outputs` are strings as seen by the engine; they are **not**
  resolved to any global root by the engine.
* Optional fields are **omitted** or set to `null` (never `""`) when not
  applicable.
* Arrays are used instead of `null` for “zero entries” (e.g., `tables: []`).

Everything in this document refers to **artifact schema v1**:
`"schema": "ade.artifact/v1", "version": "1.0.0"`.

---

## 4. `run` section

Run-level info and outcome:

```jsonc
"run": {
  "id": "run-uuid",
  "status": "succeeded",
  "started_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:00:05Z",
  "outputs": [
    "normalized.xlsx"
  ],
  "engine_version": "0.2.0",
  "error": null
}
```

### 4.1 Fields

* `id: str`  
  Unique per engine run (generated by the engine).

* `status: "succeeded" | "failed"`  
  Final outcome of the run.

* `started_at: str`  
  When the engine began processing, in UTC.

* `completed_at: str | null`  
  Time the run finished (success or failure). On some catastrophic errors this
  may be `null`, but the artifact must still be valid JSON.

* `outputs: string[]`  
  Paths (usually filenames) of normalized workbooks written by the engine.
  Typically a single entry, but more are allowed in future writer modes.

* `engine_version: str`  
  Version of `ade_engine` that produced this artifact.

* `error: object | null`  
  When `status == "failed"`, contains error summary:

  ```jsonc
  {
    "code": "config_error | input_error | hook_error | pipeline_error | unknown_error",
    "stage": "initialization | load_config | extracting | mapping | normalizing | writing_output | hooks",
    "message": "Human-readable summary",
    "details": {
      "exception_type": "ValueError",
      "exception_message": "...",
      "stage_detail": "optional free-form stage info"
    }
  }
  ```

  For successful runs, `error` is `null`.

---

## 5. `config` section

Metadata about the config and manifest used for the run:

```jsonc
"config": {
  "schema": "ade.manifest/v1",
  "version": "1.2.3",
  "name": "My Config Name"
}
```

* `schema: str`  
  Manifest schema tag, e.g. `"ade.manifest/v1"`.

* `version: str`  
  The `version` field from `manifest.json` (semver recommended).

* `name: str | null`  
  Human-readable config name from `manifest.name`, or `null` if absent.

This lets you quickly answer “which version of which config produced this
artifact?” without opening the manifest.

---

## 6. `tables` section

Each element in `tables` describes one **logical table** detected in the input:

```jsonc
"tables": [
  {
    "source_file": "input.xlsx",
    "source_sheet": "Sheet1",
    "table_index": 0,
    "header": {
      "row_index": 5,
      "cells": ["ID", "Email", "..."]
    },
    "mapped_columns": [
      {
        "field": "member_id",
        "header": "ID",
        "source_column_index": 0,
        "score": 0.92,
        "contributions": [
          {
            "detector": "ade_config.column_detectors.member_id.detect_header_synonyms",
            "delta": 0.6
          },
          {
            "detector": "ade_config.column_detectors.member_id.detect_value_shape",
            "delta": 0.32
          }
        ]
      }
    ],
    "unmapped_columns": [
      {
        "header": "Notes",
        "source_column_index": 5,
        "output_header": "raw_notes"
      }
    ],
    "validation_issues": [
      {
        "row_index": 10,
        "field": "email",
        "code": "invalid_format",
        "severity": "error",
        "message": "Email must look like user@domain.tld",
        "details": {
          "value": "foo@",
          "pattern": ".*@.*\\..*"
        }
      }
    ]
  }
]
```

### 6.1 Per-table metadata

* `source_file: str`  
  Basename of the file that contained the table (e.g. `"input.xlsx"`).

* `source_sheet: str | null`  
  Excel sheet name, or `null` for CSV.

* `table_index: int`  
  0-based ordinal of the table within that sheet (supports multiple tables per
  sheet).

* `header: object`

  * `row_index: int` – 1-based row index of the header within the sheet.
  * `cells: string[]` – header cells as strings.

The **identity** of a table is `(source_file, source_sheet, table_index)`.

### 6.2 `mapped_columns`

Each entry describes how a canonical field was mapped:

* `field: str`  
  Canonical field ID from `manifest.columns.fields`.

* `header: str`  
  Header text from the original sheet for this column (normalized).

* `source_column_index: int`  
  Zero-based column index within the raw table.

* `score: number`  
  Final mapping score for `(field, column)` after aggregating detector scores.

* `contributions: {detector, delta}[]`  
  How `score` was built:

  * `detector: str` – fully qualified function name (or a stable ID).
  * `delta: number` – contribution to the score.

This makes column mapping explainable: you can see **why** a column was chosen
for a field.

### 6.3 `unmapped_columns`

Each entry represents a physical input column that did **not** map to any
canonical field:

* `header: str`  
  Original header text.

* `source_column_index: int`  
  Zero-based index in the raw table.

* `output_header: str`  
  Generated header for this column in the normalized workbook (e.g.
  `"raw_notes"`), derived from writer settings.

If `writer.append_unmapped_columns` is `false` in the manifest, the engine may
omit or empty `unmapped_columns` because those columns are dropped entirely.

### 6.4 `validation_issues`

Each validation issue is recorded **per field, per row**:

* `row_index: int`  
  1-based original sheet row index.

* `field: str`  
  Canonical field name.

* `code: str`  
  Short identifier such as `"missing_required"`, `"invalid_format"`,
  `"out_of_range"`, `"future_date"`.

* `severity: str`  
  At least `"error"` and `"warning"`; engines and configs may define more
  (e.g. `"info"`).

* `message: str`  
  Human-readable explanation.

* `details: object | null`  
  Optional extra structured context (e.g.,
  `{ "expected_pattern": "...", "actual_value": "..." }`).

The engine normalizes whatever validators return into this shape before writing
the artifact.

---

## 7. `notes` section

`notes` is a human-oriented log of important events or comments:

```jsonc
"notes": [
  {
    "timestamp": "2024-01-01T12:00:00Z",
    "level": "info",
    "message": "Run started",
    "details": {
      "source_files": 1,
      "config": "config-abc"
    }
  }
]
```

Each note has:

* `timestamp: str`  
  When the note was recorded.

* `level: "debug" | "info" | "warning" | "error"`  
  Severity or importance.

* `message: str`  
  Human-readable text.

* `details: object | null`  
  Optional structured details.

Sources of notes:

* Engine internals: phase transitions, high-level milestones.
* Hooks: “empty table detected”, configuration-specific messages.
* Config scripts: sparingly, for durable annotations (use telemetry for
  noisy/verbose events).

Guideline: **Use notes for narrative**, not for per-row detail. Use telemetry
for high-volume events.

---

## 8. Invariants

For artifact v1:

* `run.status ∈ {"succeeded", "failed"}`.

* When `run.status == "succeeded"`:

  * `run.outputs` is non-empty.

* When `run.status == "failed"`:

  * `run.error` is non-null and contains `message` and `code`.

* For every table:

  * `source_file` is non-empty.
  * `header.row_index ≥ 1`.
  * `header.cells` length is at least the number of `mapped_columns` and
    `unmapped_columns` that refer to this table.

* `tables`, `mapped_columns`, `unmapped_columns`, `validation_issues`, `notes`
  are arrays; “none” is represented as an empty array, not `null`.

Consumers and summarizers can rely on these invariants when building derived
views.

---

## 9. Relationship to telemetry and run summaries

The engine also writes **telemetry events** to `events.ndjson` using the
unified `ade.event/v1` envelope (see `07-telemetry-events.md` and
`11-ade-event-model.md`):

* Telemetry = **timeline** (run.started, pipeline phases, table_completed, etc.)
* Artifact = **snapshot** (final state of tables, mapping, validation).

The ADE API builds a **run summary** object (see
`12-run-summary-and-reporting.md`) by reading `artifact.json` and (optionally)
`events.ndjson`:

* computes totals like `total_rows`, `error_count`, `rows_with_issues`,
* aggregates counts by field and by file,
* attaches summary into `run.completed` events and persists it into the `runs`
  table for BI.

The engine itself does **not** compute run summaries; it only guarantees:

* `artifact.json` is complete and self-consistent, and
* `events.ndjson` is a valid `ade.event/v1` NDJSON stream.

---

## 10. Versioning & evolution

Artifact is explicitly versioned via:

* `schema` – identifies the family (e.g., `"ade.artifact/v1"`),
* `version` – semantic version for this schema family.

Minor / patch changes (additive):

* New optional fields.
* New `code` / `severity` values.
* Extra `details` keys.

Breaking changes (require new `schema` and/or major bump):

* Removing or renaming existing top-level keys.
* Changing the meaning or type of fields.
* Changing how tables are identified (`source_file` / `source_sheet` /
  `table_index` triplet).

When evolving the artifact schema, keep run summary and event schemas aligned
so downstream tools can continue to integrate them cleanly.

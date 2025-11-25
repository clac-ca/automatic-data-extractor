# Artifact JSON (`artifact.json`)

`artifact.json` is the **per‑run audit record** produced by the engine.

It is the primary, structured answer to:

> “Exactly what did the engine do to this set of spreadsheets, and why?”  

Everything else (UI, reports, analytics, AI summarization) should treat
`artifact.json` as the source of truth.

This document defines:

- File location and lifecycle.
- The **schema for artifact v1**.
- How tables, mappings, and validation are represented.
- The invariants consumers can rely on.
- How ADE API is expected to consume it.

## Terminology

| Concept        | Term in code      | Notes                                                     |
| -------------- | ----------------- | --------------------------------------------------------- |
| Run            | `run`             | One call to `Engine.run()` or one CLI invocation          |
| Config package | `config_package`  | Installed `ade_config` package for this run               |
| Config version | `manifest.version`| Version declared by the config package manifest           |
| Build          | build             | Virtual environment built for a specific config version   |
| User data file | `source_file`     | Original spreadsheet on disk                              |
| User sheet     | `source_sheet`    | Worksheet/tab in the spreadsheet                          |
| Canonical col  | `field`           | Defined in manifest; never call this a “column”           |
| Physical col   | column            | B / C / index 0,1,2… in a sheet                           |
| Output workbook| normalized workbook| Written to `output_dir`; includes mapped + normalized data|

Artifact docs stick to these names; telemetry uses the same values for
consistency.

---

## 1. File location & lifecycle

### 1.1 Where it lives

For each **engine run** there is exactly **one** artifact file:

- Path: `RunPaths.artifact_path`
- Convention: `<logs_dir>/artifact.json`

Where `<logs_dir>` is:

- Passed in via `RunRequest.logs_dir`, or
- Inferred by the engine from the input location (see runtime docs).

### 1.2 When it’s created and updated

The `FileArtifactSink` in `artifact.py` manages the lifecycle:

1. **Start of run**  
   - Creates an in‑memory artifact structure with:
     - Run info (`run.status="running"`, `run.id`, `run.started_at`, …).
     - Config metadata (`config.schema`, `config.version`, …).
     - Empty `tables` and `notes` arrays.

2. **During the run**
   - Each pipeline stage calls into the artifact sink:
     - `record_table(...)` to append table summaries.
     - `note(...)` to append human‑oriented notes.
   - This can happen multiple times (e.g., once per table).

3. **On completion (success or failure)**
   - `mark_success(outputs=...)` or `mark_failure(error=...)`:
     - Sets `run.status`.
     - Sets `run.completed_at`.
     - Writes outputs or error info.
   - `flush()` writes JSON to disk **atomically**:
     - Serialize to `artifact.json.tmp`.
     - `fsync` and rename to `artifact.json`.

### 1.3 Guarantees

For **every** engine run (even failed ones):

- `artifact.json` exists at `RunPaths.artifact_path`.
- It is well‑formed JSON.
- `run.status` is either `"succeeded"` or `"failed"`.

---

## 2. Design goals

The artifact schema is intentionally:

- **Human‑inspectable**  
  Easy to read in an editor or pretty‑printed for debugging.

- **Stable & versioned**  
  Changes are additive where possible; breaking changes bump `version`.

- **Downstream friendly**  
  ADE API, reporting, and AI agents can:
  - Reconstruct mapping decisions.
  - Count validation issues by field/code/severity.
  - See how many tables were processed and from which sheets.

- **Backend‑run‑agnostic**
  No first‑class orchestration concept. Backend correlation data (run IDs, config IDs, workspace IDs) lives in telemetry, not in `artifact.json`.

- **Deliberately minimal**  
  Artifact is the stable, human‑readable audit log: run‑level info, compact
  mapping summaries (with per-column contributions), compact validation summaries,
  and high‑level notes. Per-row or debug chatter belongs in telemetry
  (`events.ndjson`), not in `artifact.json`, to keep artifacts small even on large runs.

---

## 3. Top‑level schema (v1)

Artifact JSON v1 has this high‑level shape:

```jsonc
{
  "schema": "ade.artifact/v1",
  "version": "1.0.0",

  "run": { ... },
  "config": { ... },
  "tables": [ ... ],
  "notes": [ ... ]
}
````

### 3.1 Types and conventions

Across the schema:

* All timestamps are **ISO 8601** strings in UTC (e.g. `"2024-01-01T12:00:00Z"`).
* File paths in `outputs` are strings relative to whatever the worker passes
  into the engine; they are **not** normalized to any global root.
* Optional fields are omitted or set to `null` (never the empty string) when
  not applicable.

Everything in this document refers to **artifact schema v1**:
`"schema": "ade.artifact/v1", "version": "1.0.0"`.

---

## 4. `run` section

Run‑level info and outcome:

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
  Time run started (pipeline initialization) in UTC.

* `completed_at: str | null`
  Time run completed (success or failure).
  May be `null` if an unrecoverable error occurs before the engine can set it
  (but the artifact file will still be valid JSON).

* `outputs: string[]`
  Paths (usually file names) of output workbooks written by the engine.
  Typically length 1, but future writer modes may emit more.
* `engine_version: str`
  Version of `ade_engine` that produced the artifact.

* `error: object | null`
  If `status == "failed"`, contains error summary with structured code + stage + message.
  Recommended shape:

  ```jsonc
  {
    "code": "config_error | input_error | hook_error | pipeline_error | unknown_error",
    "stage": "initialization | load_config | extracting | mapping | normalizing | writing_output | hooks",
    "message": "Human-readable summary",
    "details": {
      "exception_type": "ValueError",
      "exception_message": "...",
      "stage_detail": "... optional free-form stage info ..."
    }
  }
  ```

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

### 5.1 Fields

* `schema: str`
  Manifest schema tag, e.g. `"ade.manifest/v1"`.

* `version: str`
  Value of `version` from `manifest.json` (semver recommended).

* `name: str | null`
  Human‑readable name from `manifest.name`, or `null` if not provided.

This section lets you answer “which config produced this artifact?” quickly,
without opening the manifest.

---

## 6. `tables` section

Each element in `tables` describes one logical table detected in the input:

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
            "delta": 0.60
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

### 6.1 Per‑table metadata

* `source_file: str`
  Basename of the source file where the table was found
  (e.g., `"input.xlsx"` or `"members.csv"`).

* `source_sheet: str | null`
  Excel sheet name, or `null` for CSV.

* `table_index: int`
  0-based order of the table within the sheet (supports multiple tables per sheet).

* `header: object`

  * `row_index: int` — 1‑based row index within the sheet.
  * `cells: string[]` — header row cells as strings.

The **table identity** is `(source_file, source_sheet, table_index)`; `header.row_index`
is still recorded for traceability.

### 6.2 `mapped_columns` entries

Each item describes how one canonical field was mapped:

* `field: str`
  Canonical field name (from manifest `columns.fields`).

* `header: str`
  Original header text from the source file that was mapped to this field
  (post simple normalization).

* `source_column_index: int`
  Zero‑based index of the column in the raw table.

* `score: number`
  Final matching score for this `(field, column)` after aggregating detector
  contributions.

* `contributions: {detector, delta}[]`
  Fine‑grained breakdown of how `score` was built:

  * `detector: str` — fully qualified function name or a stable ID.
  * `delta: number` — contribution added by that detector.

This structure makes it possible to reconstruct **why** a column mapped to a
field, not just that it did.

### 6.3 `unmapped_columns` entries

Each `unmapped_columns` entry represents a source column that was not mapped to any
canonical field but is preserved in the normalized output:

* `header: str`
  Original header text.

* `source_column_index: int`
  Zero‑based index in the raw table.

* `output_header: str`
  Generated header used for this column in the normalized workbook
  (e.g. `raw_notes`), based on writer settings.

If `writer.append_unmapped_columns` is `false` in the manifest, the
engine may omit `unmapped_columns` entries (or leave the array empty) because those
columns are dropped entirely.

### 6.4 `validation_issues` entries

Each validation issue is recorded **per field, per row**:

* `row_index: int`
  1‑based original row index in the sheet (consistent with extraction).

* `field: str`
  Canonical field name.

* `code: str`
  Short, machine‑friendly identifier, e.g. `"invalid_format"`,
  `"missing_required"`, `"out_of_range"`.

* `severity: str`
  At least:

  * `"error"`
  * `"warning"`
    Additional severities may be defined later (e.g. `"info"`).

* `message: str`
  Human‑readable explanation suitable for UI display.

* `details: object | null`
  Optional structured data to support richer UIs:

  * e.g. `{ "expected_pattern": "...", "actual_value": "..." }`.

The engine normalizes any issues returned by validators into this shape before
writing the artifact.

---

## 7. `notes` section

`notes` is a human‑oriented timeline of important events or comments:

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

### 7.1 Fields

Each note entry contains:

* `timestamp: str`
  When the note was recorded.

* `level: "debug" | "info" | "warning" | "error"`
  Severity or importance of the note.

* `message: str`
  Human‑readable text.

* `details: object | null`
  Optional structured data (free‑form).

### 7.2 Sources of notes

Notes may be produced by:

* The engine itself:

  * Phase transitions, key milestones.
* Hooks:

  * `on_run_start`, `on_after_extract`, `on_after_mapping`, etc.
* Config scripts:

  * Via the provided `artifact` or `logger` APIs (used sparingly for enduring
    notes; otherwise prefer telemetry).

**Guideline:**

Use `notes` for high‑level narrative. Use telemetry (`events.ndjson`) for
more granular event streams.

**Boundary:**

Keep `artifact.json` compact: run info, compact mapping summaries (with
per-column contributions), validation summaries, and durable notes. Put
per-row debug or verbose detector outputs into telemetry events instead of
artifact.

---

## 8. Behavior & invariants

The following **invariants** hold for artifact v1:

* `run.status ∈ {"succeeded", "failed"}`.
* When `status == "succeeded"`:

  * `run.outputs` has at least one entry.
* When `status == "failed"`:

  * `run.error` is non‑null and contains a `message`.
* For every table:

  * `source_file` is non‑empty string.
  * `header.row_index ≥ 1`.
  * `header.cells` length equals `mapped_columns.length + unmapped_columns.length` if the
    writer is configured to preserve all columns.
* `tables`, `mapped_columns`, `unmapped_columns`, `validation_issues`, `notes` are arrays;
  missing values are represented as empty arrays, not `null`.

Backends can safely rely on these when building UI and reporting logic.

---

## 9. Versioning & evolution

Artifact is explicitly versioned via:

* `schema` — identifies the “family” (e.g., `"ade.artifact/v1"`).
* `version` — semantic version for this family.

### 9.1 Minor changes

Allowed without bumping `schema` and with minor/patch bumps of
`version`:

* Adding optional fields.
* Adding `details` sub‑fields.
* Adding new `code` / `severity` values.

Consumers should ignore unknown fields.

### 9.2 Breaking changes

Require either:

* A new `schema` (e.g. `"ade.artifact/v2"`), or
* A major bump in `version` and clear migration plan.

Breaking changes include:

* Removing or renaming top‑level keys.
* Changing the meaning or type of existing fields.
* Changing how tables are keyed or identified.

---

## 10. How ADE API should use `artifact.json`

Typical usage patterns:

* **Run summary page (in backend UI)**

  * Use `run.status`, `run.error`, and `run.outputs`.
  * Show config `name` and `version`.

* **Field mapping explanation**

  * For each table:

    * Show `mapped_columns` rows: canonical field → source header + score.
    * Show `unmapped_columns` and their generated `output_header`.

* **Data quality reporting**

  * Aggregate `validation_issues` entries across tables:

    * counts by `field`, `code`, `severity`.
    * top rows with many issues.
  * Provide drill‑down views: “show me all rows where `member_id` is missing”.

* **AI‑assisted explanations**

  * Use `tables[*].mapped_columns`, `validation_issues`, `notes`, and run outputs as the
    primary context to explain:

    * how the engine interpreted the file,
    * what problems were found,
    * how severe they are.

`events.ndjson` (telemetry) complements `artifact.json` with a fine‑grained
event stream, but `artifact.json` is the canonical, stable run summary.

# Overview

`ade-engine` (“ADE engine”) normalizes messy spreadsheets into a canonical, schema-aligned workbook.

At a high level, it:

1. Loads a source workbook (`.xlsx` or `.csv`).
2. Iterates sheets (optionally filtered).
3. Detects one or more **table regions** per sheet.
4. Extracts a header row + data rows from each region.
5. Maps source columns to canonical fields using **column detector functions**.
6. Applies **transforms** and **validators** to produce normalized rows and issues.
7. Writes normalized tables into an output workbook.

The engine is **configuration-driven**. A separate Python package (default: `ade_config`) contains:

- `manifest.toml`: schema and hook wiring
- column detector modules: `column_detectors/<field>.py`
- row detector modules: `row_detectors/*.py`
- optional hook modules: `hooks/*.py`

The config package is loaded dynamically at runtime, so you can ship multiple schemas/configurations without changing the engine.

---

## Key concepts

### Canonical schema
The schema is defined in `manifest.toml` under `[[columns]]`. Each column has a canonical `name` (used in outputs) plus attributes like `label`, `required`, and `synonyms`.

### Table region
A **table region** is a rectangular bounding box in source worksheet coordinates:
`min_row..max_row`, `min_col..max_col`.

Table regions are detected using **row detectors**. The default policy looks for a “header row” followed by contiguous “data rows”.

### Column detector
A column detector is a function named `detect_*` inside a column module. Detectors score how well a source column matches a canonical field.

Detectors are pluggable and can be heuristic or data-driven. The engine simply calls them and aggregates scores.

### Transformer and validator
A column module may also define:

- `transform(...) -> dict | None`: returns field updates to apply to the row
- `validate(...) -> list[dict] | None`: returns validation issue dicts

### Hooks
Hooks are lifecycle callables that can observe or modify the run.

Notably, `on_table_mapped` may return a `ColumnMappingPatch` to override mapping decisions.

### Reporting
The engine supports two “reporting” outputs:

- **text:** readable log lines (default; typically stderr)
- **ndjson:** structured JSON objects, one per line (stdout or a file)

Both modes use the same internal API: `logger` + `events`.

---

## When to use ade-engine

Use `ade-engine` when you need:

- repeatable spreadsheet normalization
- schema-driven transforms and validations
- rich progress/events for UI streaming
- an engine that is easy to embed in a service

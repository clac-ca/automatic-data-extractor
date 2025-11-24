# 04 — Column Mapping

Column mapping is the step where `ade_engine` turns a raw worksheet (rows and columns of cells) into a stable, named schema that hooks and downstream systems can rely on.

At a high level:

```text
Workbook / CSV
    ↓
Parsing & row classification (row detectors)
    ↓
Column detection (column detectors)
    ↓
Column mapping
    ↓
Normalized rows exposed to hooks & outputs
```

This document explains:

* What *physical* vs *logical* columns are.
* What inputs column mapping consumes.
* How the mapping is produced and validated.
* How hooks and other parts of the engine use the mapping.
* What guarantees the engine tries to maintain.

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

This chapter uses “field” exclusively for manifest entries and “column” for
cells in a sheet. Avoid other synonyms.

---

## Goals

Column mapping is designed to:

1. **Decouple sheet layout from business logic**
   Config packages describe *logical* columns (“invoice_number”, “amount_due”). Column mapping hides whether those live in column B vs column F, or across different sheets.

2. **Provide a stable, named schema for hooks**
   Hooks should work with dictionaries like `{"invoice_number": "...", "amount_due": ...}` instead of worrying about Excel coordinate math.

3. **Allow multiple detection strategies**
   Different column detectors can vote on where a field lives. The mapping step combines those signals into a single, deterministic choice.

4. **Fail loudly when required columns are missing**
   If the configuration says a column is required, column mapping is the place where that gets enforced.

5. **Be explainable and debuggable**
   It should be obvious *why* a column was mapped where it was (or why it’s missing) by inspecting logs/artifacts.

---

## Core Concepts

### Physical columns

A **physical column** is “whatever Excel/CSV calls a column”:

* Identified by:

  * `sheet_name` (or index),
  * `column_index` (0‑based internally; script APIs receive 1‑based and the engine converts) or column letter,
  * and the set of cell values in that column.
* Completely layout‑driven: if the source file changes shape, the physical columns change.

Examples:

* Column `B` on sheet `"Detail"` in an XLSX file.
* Column `0` in a CSV with no sheets.

### Fields (canonical columns)

A **field** is a semantic, canonical data element defined by the config manifest, for example:

* `invoice_number`
* `bill_to_name`
* `line_amount`
* `posting_date`

Fields:

* Are described in the config manifest (name, type, whether required, etc.).
* Do **not** know where they live in the sheet(s) until mapping assigns a physical column.
* Are the keys hooks and outputs use.

Column mapping’s role is to say:

> “For this document and sheet, field `invoice_number` is implemented by physical column B.”

### Detections

**Column detectors** are small pieces of config code that look at the raw sheet and emit *detections* such as:

* “Column B looks like `invoice_number` with score 0.92.”
* “Column F is probably `amount_due` but the header is slightly off.”

Each detection is conceptually:

```text
DetectorFinding:
  field_id            # which field this relates to
  sheet_id            # which sheet / tab
  column_index        # which physical column
  score               # confidence or quality signal
  reasons             # optional free‑form explanation / features
```

Different detectors can propose different columns for the same field; column mapping resolves these into a single choice.

### Column map

The **column map** is the main output and lives on `MappedTable.column_map`:

```text
ColumnMap:
  mapped_columns: list[MappedColumn]      # one per field that mapped
  unmapped_columns: list[UnmappedColumn]  # physical columns with no field match

MappedColumn:
  field              # field ID from manifest.columns.order/fields
  header             # header text from the source sheet (if any)
  source_column_index# 0-based physical column index
  score              # aggregate mapping score
  contributions      # list[ScoreContribution] per detector
  is_required        # from manifest
  is_satisfied       # True if a physical column was chosen
```

The exact Python fields may vary, but the names above are used consistently in
docs, artifact, and telemetry.

---

## Inputs to Column Mapping

Column mapping runs once the engine has:

1. **Parsed workbook / CSV**

   * A grid of cells with:

     * raw value,
     * possibly formatted value,
     * row/column indices,
     * sheet metadata.
   * For XLSX, ADE has already chosen which sheet(s) to operate on for this run.

2. **Row classifications (optional but typical)**

   Row detectors may have classified rows as:

   * header row(s),
   * data rows,
   * footer/summary rows,
   * noise (blank, separators, etc.).

   Column detectors can use this to focus on plausible header rows and data samples.

3. **Column detector outputs**

   All column detectors within the active config package have been run. Their findings are aggregated into a common in‑memory representation (as outlined above).

4. **Config manifest schema**

   The manifest describes:

   * the list of fields,
   * what they are called,
   * whether they’re required or optional,
   * sometimes hints like expected type/pattern (dates, numbers, strings).

   Column mapping uses this to know *what* to look for and *how strict* to be.

---

## Outputs of Column Mapping

When column mapping completes, the engine has:

1. **A resolved `ColumnMap` per sheet**

   For each sheet being processed:

   * `column_map.mapped_columns` contains the fields that were matched, each with `is_required`/`is_satisfied` flags.
   * `column_map.unmapped_columns` lists physical columns that did not match any field (useful for appending `raw_` extras).
   * If multiple physical columns were plausible, the chosen winner is recorded along with tie‑breaking details.

2. **Validation results**

   * If required columns are missing, the mapping stage produces structured errors.
   * These can:

     * fail the run early, or
     * be surfaced as warnings depending on engine/config settings.

3. **A normalized row accessor**

   Downstream, hooks receive **normalized rows** that look like:

   ```python
   row["invoice_number"]  # value from whichever physical column was mapped
   ```

   instead of:

   ```python
   row[3]  # pray this is still the invoice number column
   ```

4. **Debug/observer data**

   Mapping decisions are recorded into the run’s debug artifacts (run logs and artifact JSON) so that UIs and developers can understand what happened when a run misbehaves.

---

## Mapping Pipeline

This section describes the mapping algorithm in broad strokes. Many details are implementation‑specific, but the high‑level flow is intentionally stable.

### 1. Candidate generation

For each sheet:

1. The engine enumerates physical columns that are plausible data columns (e.g., non‑empty, not clearly metadata‑only).
2. Each column detector runs and emits zero or more `DetectorFinding` objects.

For a single field you might end up with:

```text
field_id = "invoice_number"

Candidates:
  B: score 0.92 (header match: "Invoice #")
  C: score 0.35 (data looks like alphanumeric IDs, header is blank)
  F: score 0.10 (weak pattern match)
```

Detectors can contribute different kinds of evidence:

* header text similarity,
* sample value patterns,
* position relative to other known columns (“amount_due usually appears after quantity”),
* config hints (e.g., “prefer columns named `Invoice #` or `Inv Num`”).

### 2. Scoring and aggregation

The engine then aggregates detector findings:

* Group findings by `(sheet_id, field_id, column_index)`.
* Merge scores from multiple detectors into a **combined score**.

  * E.g., weighted sum, max, or any heuristic the engine uses.
* Normalize scores so they’re comparable across columns.

At this point, for each field and sheet, you have a ranked list:

```text
invoice_number:
  B (score 0.92, detectors: header, pattern)
  C (score 0.35, detectors: pattern only)
  F (score 0.10, detectors: weak header match)

amount_due:
  F (score 0.88, detectors: header, numeric)
  G (score 0.20, detectors: numeric)
  ...
```

### 3. Winner selection

For each `(sheet_id, field_id)` pair, the engine chooses:

* The **best candidate** whose score clears a configurable threshold.
* If no candidate meets the threshold, the field is **unmapped** on that sheet.

Tie‑breaking typically prefers:

1. Higher combined score.
2. Columns whose headers are “cleaner” matches to the field name or its configured aliases.
3. Columns nearer to other high‑confidence columns from the same "family" (e.g., `quantity`, `unit_price`, `amount_due`).

### 4. Building the `ColumnMap`

Once winners are selected:

* Build a `ColumnMap` instance with two lists:

  * `mapped_columns`: one `MappedColumn` per field that cleared the score threshold (record `source_column_index`, `header`, `score`, `contributions`, `is_required`, `is_satisfied`).
  * `unmapped_columns`: one `UnmappedColumn` per physical column that did not map to any field (used later for `raw_` extras if enabled).
* Attach this `ColumnMap` to `MappedTable.column_map`.

The resulting map:

* Is **deterministic** for a given config + document.
* Is **stable** even if detectors are internally refactored, as long as their output semantics stay the same.

### 5. Validation and error reporting

With a `ColumnMap` in hand, the engine validates against the config manifest:

* For each required field:

  * If `is_satisfied` is `False`, add a validation error like:

    > `missing_required_column: invoice_number`
* Optionally check expected data types or patterns using sample values from the mapped column (e.g., “95% of values should parse as dates”).

Configuration or runtime settings control whether:

* the run fails fast (“hard” validation), or
* the run continues but reports missing columns as warnings (“soft” validation).

---

## How Hooks Use Column Mapping

Hooks should never need to look at physical row/column indices.

Instead, hooks see **normalized rows** where keys are field IDs:

```python
def process_row(row, context):
    # `row` is keyed by fields from the config manifest
    invoice_no = row["invoice_number"]
    amount = row["amount_due"]
    posted_at = row.get("posting_date")  # may be None if optional/unmapped

    # Business logic here...
```

This is made possible by column mapping:

1. When the engine streams data rows, it uses the `ColumnMap` to:

   * resolve which physical column(s) provide each field value,
   * pull the corresponding cell from the current physical row,
   * optionally coerce/normalize the value (dates, decimals, etc.).
2. The hook receives a **field-identified view** of the row and never sees raw column indices.

**Important invariants for hooks:**

* The set of keys in `row` matches the fields defined in the manifest.
* Missing required columns will normally prevent hooks from running (unless configured otherwise).
* Optional fields may be present but unmapped; in that case their value will typically be `None`.

---

## Multiple Sheets and Tables

ADE’s backend can associate a run with one or more sheets in a workbook:

* Column mapping is **per sheet**:

  * each sheet gets its own `ColumnMap`;
  * hooks may run per sheet or over a combined view, depending on configuration.

Common patterns:

* **Single‑sheet runs**
  The config expects to operate on one sheet (e.g., “Detail”). Column mapping only runs for that sheet.

* **Multi‑sheet runs**
  Some configs may want to:

  * process multiple sheets with the same schema (e.g., monthly tabs), or
  * process different sheets with different schemas (e.g., `Header` vs `Detail` tables).

The column mapping layer is responsible for:

* Ensuring each `(sheet_id, field_id)` is resolved independently.
* Exposing which sheets are “active” for a given run so hooks can iterate accordingly.

---

## Designing Column Detectors for Good Mapping

Column mapping quality is only as good as the signals it receives. When authoring `column_detectors` in a config package:

1. **Prefer clear, narrow responsibilities**

   * One detector can focus on header names.
   * Another can focus on sample data patterns (dates, currency, etc.).
   * A third can use relative position between columns.

2. **Emit scores, not yes/no answers**

   * Use scores to express confidence (0.0–1.0 or similar).
   * Column mapping can then decide how to combine and threshold them.

3. **Explain your decisions**

   * Include brief textual “reasons” in your findings where practical.
   * These surface nicely in logs and make debugging much easier.

4. **Handle noisy real‑world data**

   * Look for common variations in headers (e.g., “Invoice #”, “Inv No”, “Invoice Num”).
   * Be resilient to extra whitespace, casing, and punctuation.

5. **Fail usefully**

   * If a detector is unsure, prefer emitting a low‑confidence candidate rather than nothing.
   * Mapping can drop it based on thresholds, but seeing the candidate in debug output helps diagnostics.

---

## Failure Modes and Debugging

When column mapping goes wrong, you typically see one of:

* Required column reported as missing.
* Hooks throwing `KeyError` for a field you expected to be mapped.
* Output files with values shifted or clearly mismatched to their headers.

To debug:

1. **Inspect the run artifact / logs**

   Look at the run’s artifact JSON and/or event log for:

   * The final `ColumnMap`:

     * which physical columns were mapped,
     * any missing required columns.
   * Detector findings:

     * did a detector emit a candidate at all?
     * what score did it assign?

2. **Compare the manifest to the sheet**

   * Is the field defined with the name/aliases you expect?
   * Did the header wording in the file change (e.g., from “Invoice #” to “Invoice ID”)?

3. **Check thresholds / configuration**

   * If a candidate has a decent but not great score, perhaps the detection threshold is too strict.
   * Conversely, if the mapping is clearly wrong, thresholds may be too loose.

4. **Refine detectors**

   * Add or adjust detectors to better handle the new layout.
   * Add more robust header and pattern matching.

---

## Summary

Column mapping is the bridge between raw spreadsheet shape and the field schema your config package defines. It:

* combines signals from `column_detectors`,
* chooses a single physical column for each field,
* enforces required vs optional columns,
* and presents hooks with simple, named `row["field_name"]` access.

As long as you think in terms of *fields* and keep column detectors focused and expressive, the engine can adapt to messy, real‑world spreadsheets while keeping your hooks and outputs stable.

# Supporting docs — ADE run summary (`engine.run.completed`)

This document explains the semantics and intent of the `engine.run.completed` payload (schema v1).

---

## Why this event exists

We need a single, authoritative record answering:

> “How successful was ADE on this input, and why?”

This is intentionally different from step-by-step logs:

- Step logs explain *what happened during processing*.
- The summary explains *what ADE believes the structure is*, *how complete/confident that belief is*, and *why anything was not mapped*.

The summary is designed to be:

- **machine-friendly**: stable reason codes, predictable structure, strict types
- **human-friendly**: hierarchical structure with mapping detail at the table level
- **failure-tolerant**: emitted exactly once per run, even on exceptions

---

## Scope hierarchy

The summary is hierarchical:

- run
  - workbooks[]
    - sheets[]
      - tables[]

Tables are the ground truth. Higher levels are rollups.

---

## Indexing conventions

- `workbook.index`, `sheet.index`, `table.index` are **0-based**.
- `structure.header.row_start` and `structure.data.row_start` are **1-based** row numbers (spreadsheet-style).

---

## Emptiness and sparsity

### Empty cell

A cell is considered empty if:

- value is `null`, OR
- a string that becomes empty after trimming whitespace.

### Empty row

A data row is empty if **all cells in the row** (over physical columns) are empty.

### Empty column

A physical column is empty if **all data cells in that column** are empty.

### Cells rollup (optional but recommended)

`cells.total` and `cells.non_empty` provide a direct “data density” measure. This is often the simplest indicator of sparse inputs.

---

## Counts semantics (v1)

### What is summed (rollups)

Unless stated otherwise, rollups are **sums across child tables** within the scope:

- `counts.rows.*`
- `counts.columns.*`
- `counts.cells.*`
- `validation.rows_evaluated`
- `validation.issues_total`
- `validation.issues_by_severity[*]`

`validation.max_severity` is the **maximum** severity observed in the scope.

### What is de-duplicated

Some values are intentionally **not** sums:

- `counts.fields.expected` is the configured canonical field count (per config package).
- `counts.fields.mapped` is **the number of expected fields mapped at least once in this scope**
  (a field is counted once even if it appears in multiple tables).

---

## Mapping semantics (column → field)

### Physical columns vs configured fields

- **Physical columns** are what ADE observes in a detected table region.
- **Fields** are the configured canonical schema (what the config package expects).

### Mapping outcomes per physical column

Each table column has a `mapping.status`:

- `mapped`
  - selected `field`, `score`, and `method` are present
  - `unmapped_reason` is absent
- `ambiguous`
  - candidates exist but **no selected field** is chosen
  - candidates list is present and non-empty
  - `unmapped_reason` is required
- `unmapped`
  - no selected field
  - `unmapped_reason` is required
  - candidates optional
- `passthrough`
  - explicitly treated as raw/unmapped output due to policy
  - no selected field
  - `unmapped_reason` must be `passthrough_policy`
  - candidates optional

### Candidate list (v1)

Candidates are used for analysis like:

- “was the correct field second-best?”
- “which fields are frequently confused?”

To keep payloads small:

- candidates are capped to top **N=3**
- candidates are sorted by descending score

### Stable unmapped reasons (v1)

For machine-friendly reporting, ambiguous/unmapped/passthrough mappings include a stable `unmapped_reason`:

- `no_signal`
- `below_threshold`
- `ambiguous_top_candidates`
- `duplicate_field`
- `empty_or_placeholder_header`
- `passthrough_policy`

---

## Sheet scan semantics (optional)

`sheet.scan` describes the sheet-level row materialization step (not the detected table size):

- `rows_emitted`: how many rows were emitted from scanning/materializing the sheet
- `stopped_early`: whether scanning stopped due to a limit or early exit policy
- `truncated_rows`: how many rows were skipped due to truncation policy

`scan` is orthogonal to `counts.rows.total` at table scope, which describes the detected table region.

---

## Outputs semantics (v1)

`outputs.normalized` is a pointer to a normalized output artifact *only when it is actually written*.

- At run scope, `outputs.normalized.path` points to the normalized workbook output.
- At table scope, `outputs.normalized` may include `sheet_name` and `range_a1` to locate the normalized table in the output workbook.

If output writing fails, outputs pointers **must be omitted** to avoid misleading consumers.

---

## Execution vs evaluation

We separate two concerns:

- `execution`: runtime completion (succeeded/failed/cancelled, timestamps, failure details)
- `evaluation`: semantic success (how well ADE understood the input)

This prevents “status=succeeded” from hiding that mapping quality was poor.

**v1 scope rule:** `execution` and `evaluation` appear at **run scope only** to avoid contradictory per-scope statuses.

---

## Evaluation grading (recommended v1 rule set)

A simple, explainable grading rule set:

1) If `execution.status == "failed"` and **no tables** were summarized:
- outcome: `unknown`
- finding: `execution_failed`

2) Otherwise, base outcome from summarized structure:

- If `counts.tables == 0`: `failure` + finding `no_tables_detected`
- Else if `counts.fields.mapped == 0`: `failure` + finding `no_fields_mapped`
- Else if `counts.fields.mapped < counts.fields.expected`: `partial` + finding `fields_unmapped`
- Else: `success`

3) Add validation findings:

- If validation warnings exist: add `validation_warnings_present`
- If validation errors exist (future severity): add `validation_errors_present` and typically downgrade `success` → `partial`

4) Add execution findings:

- If `execution.status == "failed"` but some tables were summarized:
  add finding `execution_failed` (and typically outcome remains `partial`)

Findings should use stable `code` values for dashboards.

---

## Payload size policy (v1)

To avoid payload bloat:

- Detailed mapping lives only at **table scope** (`structure.columns[*].mapping`)
- Run scope has a single `fields[]` rollup (field-centric view)
- Workbook/sheet/table rollups include only `counts` + `validation` (+ optional scan/outputs)

# Supporting docs — ADE run summary (`engine.run.completed`)

This document provides context and rationale for the work package.

## Why this event exists

We need a single, authoritative record answering:

> “How successful was ADE on this input, and why?”

This is distinct from step-by-step debug logs:
- Step logs explain *what happened*.
- The summary explains *what ADE believes the structure is* and *how complete/confident that belief is*.

## Key decisions (v1)

### Event identity and versioning
- **Event name** `engine.run.completed` is the schema identity.
- Payload includes **`schema_version` only**, so consumers can adapt across versions.
- `schema_version` is an **int major**. For v1: `schema_version=1`.
- Emission uses the engine logger namespace: code calls `logger.event("run.completed", ...)` and the logger qualifies it as `engine.run.completed`.

### Execution vs evaluation
We separate two concerns:

- `execution` — runtime success/failure (did the run finish?)
- `evaluation` — semantic understanding success (did ADE understand the data?)

This prevents the common confusion where “status=success” hides that mapping was poor.

### Standard naming choices
- `outputs` (not “artifacts”): clearer and conventional.
- `failure` (not “error” inside payload): avoids collision with log envelope `error`.

### Scope hierarchy
The summary is hierarchical:

- run
  - workbooks[]
    - sheets[]
      - tables[]

Tables are the ground truth; higher levels are rollups.

## Emptiness and sparsity

### Empty cell definition
A cell is considered empty if:
- value is `None` / null
- or a string that becomes empty after trimming whitespace

### Empty row definition
A data row is empty if all cells in the row (over physical columns) are empty.

### Empty column definition
A physical column is empty if all data cells in that column are empty.

### Why include cell totals (optional)
`cells.total` and `cells.non_empty` give a direct “data density” measure, which is often the simplest indicator of sparse inputs.

## Mapping semantics

### Physical columns vs configured fields
- **Physical columns** are what ADE observes in the detected table region.
- **Fields** are what the config package defines as the canonical schema.

### Mapping outcomes per physical column
Each table column mapping has a `status`:
- `mapped`: assigned to a single field
- `ambiguous`: candidates exist but **no selected field** is chosen (decision is not stable/safe)
- `unmapped`: no assignment
- `passthrough`: treated as raw/unmapped output (if you later formalize it)

### Why include candidates
Candidates allow analysis like:
- “was the correct field second-best?”
- “which fields are frequently confused?”

To keep payloads small, we cap candidate lists to top-N.

### Unmapped/ambiguous reasons (v1)
For machine-friendly reporting, include a stable `unmapped_reason` for `ambiguous` and `unmapped` mappings:

- `no_signal`
- `below_threshold`
- `ambiguous_top_candidates`
- `duplicate_field`
- `empty_or_placeholder_header`
- `passthrough_policy`

## Evaluation grading (v1 suggested)

A simple, explainable grading rule set:
- If execution failed before any tables were summarized: `unknown` + finding `execution_failed`
- If zero tables detected: `failure` + `no_tables_detected`
- If fields.mapped == 0: `failure` + `no_fields_mapped`
- If any expected fields unmapped: `partial` + `fields_unmapped`
- If validation has errors: add finding `validation_errors_present` (may keep grade partial)
- Else: `success`

Findings should use stable `code` values for dashboards.

## Rollup semantics

Rollups are **sums across tables** (not “unique headers across workbook”) unless explicitly stated.

This makes metrics stable and avoids hidden de-duplication logic.

If you later need unique header aggregation for UI, add a separate `header_aggregates` section in a future schema version.

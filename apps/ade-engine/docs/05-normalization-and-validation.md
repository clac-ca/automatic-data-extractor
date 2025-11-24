# Normalization & Validation

This document describes the **normalization stage** of the ADE engine: how we
turn a `MappedTable` (columns → canonical fields) into:

- a dense, ordered matrix of normalized values, and  
- a structured list of validation issues,

wrapped in a `NormalizedTable`.

This stage is implemented in `pipeline/normalize.py` and sits between:

- **mapping** (`MappedTable`) and  
- **write** (`write_workbook`, which turns `NormalizedTable`s into Excel output).

It assumes you’ve read:

- `03-io-and-table-detection.md` (how we get `RawTable`), and  
- `04-column-mapping.md` (how we get `MappedTable`).

---

## 1. Role in the pipeline

High-level view:

```text
RawTable
  └─(mapping)─▶ MappedTable
                    └─(normalization)─▶ NormalizedTable
                                              └─(write)─▶ Excel workbook
````

**Mapping** answers: *“Which input columns correspond to which canonical fields?”*
**Normalization** answers: *“Given those fields, what are the cleaned values, and are they valid?”*

Normalization is:

* **Config-driven** — transforms and validators live in `ade_config`.
* **Row-oriented** — runs field-by-field for each input row.
* **Pure pipeline** — no IO; just data transformation plus logging/artifact updates.

---

## 2. Inputs & outputs

### 2.1 Function signature

The normalization stage is encapsulated by:

```python
def normalize_table(
    ctx: RunContext,
    cfg: ConfigRuntime,
    mapped: MappedTable,
    logger: PipelineLogger,
) -> NormalizedTable:
    ...
```

Where:

* `ctx: RunContext`

  * Per-run context (paths, manifest, env, metadata, shared `state` dict, timestamps).
* `cfg: ConfigRuntime`

  * Config runtime object exposing:

    * manifest (`ManifestContext`),
    * column registry (`ColumnModule`s with transform/validate),
    * writer defaults, etc.
* `mapped: MappedTable`

  * Output of the mapping stage:

    * `raw: RawTable`
    * `mapping: list[ColumnMapping]`
    * `extras: list[ExtraColumn]`
* `logger: PipelineLogger`

  * Unified logging/telemetry/artifact helper.

Returns:

* `NormalizedTable`

  * `mapped` — original `MappedTable`
  * `rows` — 2D list of normalized values
  * `issues` — list of `ValidationIssue`

---

## 3. Canonical row model

The core internal abstraction is a **canonical row dict**:

```python
row: dict[str, Any]   # field_name -> value
```

This is what transforms and validators read and modify.

### 3.1 Column ordering & enabled fields

Column order comes from the manifest:

* `manifest.columns.order` — ordered list of canonical field names.
* `manifest.columns.meta[field_name].enabled` — flag to include/exclude a field.

Normalization respects that order:

* **Canonical fields**:

  * Iterate over `columns.order` and include only fields where `enabled=True`.
* **Extra columns**:

  * Appended later (based on `MappedTable.extras`), after all canonical fields.

The final `NormalizedTable.rows` is ordered as:

```text
[c1, c2, ..., cN, extra1, extra2, ...]
```

where `c1..cN` follow `columns.order` and `extra*` follow `MappedTable.extras`.

### 3.2 Seeding the canonical row

For each data row in `mapped.raw.data_rows`:

1. Start with an empty `row: dict[str, Any]`.
2. For each canonical field in `manifest.columns.order`:

   * Find its `ColumnMapping` in `mapped.mapping` (if any).
   * If mapped:

     * Read the raw cell from `mapped.raw.data_rows[row_idx][mapping.index]`.
     * Set `row[field_name] = raw_value`.
   * If not mapped:

     * Set `row[field_name] = None` or a manifest-specified default if we
       introduce such behavior.
3. At this point, `row` contains **raw, unnormalized** values keyed by canonical
   field name (and no extras yet).

This seeded `row` is the input to the transform phase.

### 3.3 Row index semantics

`row_index` is always aligned to the **original sheet row index**:

* `MappedTable.raw.header_index` is the header row’s 1-based index.
* Data row `i` is at original row index:

```python
row_index = mapped.raw.first_data_index + i
```

This index is passed into transforms and validators and appears in
`ValidationIssue.row_index` and artifact records.

---

## 4. Transform phase

Transforms are **field-level functions** that clean and normalize data. They
live in `ade_config.column_detectors.<field_module>` and are optional.

### 4.1 Transformer signature

Standard keyword-only signature:

```python
def transform(
    *,
    job,                    # RunContext (named "job" for historical reasons)
    state: dict,            # shared per-run scratch space
    row_index: int,         # original sheet row index (1-based)
    field_name: str,        # canonical field
    value,                  # current value for this field
    row: dict,              # full canonical row (field -> value)
    field_meta: dict | None,
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> dict | None:
    ...
```

Parameters to remember:

* `job`: full run context (paths, metadata, env).
* `state`: mutable dict shared across all rows and scripts within this run.
* `row_index`: traceability back to original file.
* `field_name`, `value`, `row`: the core of the normalization work.
* `field_meta`: the manifest’s metadata for this field (e.g., label, required).
* `env`: config‑level environment values (locale, date formats, etc.).
* `logger`: use for notes/events (not `print`).

### 4.2 Call order & data flow

For each data row:

1. Build the **seed** canonical row as described in §3.2.
2. Iterate over canonical fields in `manifest.columns.order`:

   * For each field with a transformer:

     * Call `transform(...)` with the current `row[field]` and full `row` dict.
     * Allow the transformer to:

       * mutate `row[field]` and/or other `row` entries, and/or
       * return a dict of updates to merge into `row`.

This means:

* Transforms see the **latest state of the row** (including effects of earlier
  transforms in the same row).
* Ordering is deterministic and known: manifest order.

Because of this, config authors can:

* Treat each transform as independent (preferred), or
* Rely on left‑to‑right dependencies (e.g., parse a “full_name” before splitting
  into first/last names).

### 4.3 Return value behavior

* If `transform` returns `None`:

  * The engine assumes all updates were made in-place via `row[...] = ...`.

* If it returns a `dict`:

  * The engine merges it into `row`:

    ```python
    updates = transform(...)
    if updates:
        row.update(updates)
    ```

* Keys in `updates` that are **not** canonical fields:

  * Are allowed (e.g., to compute helper values for validators).
  * They will not appear in the final output unless later mapped by manifest.

### 4.4 Error handling

If a transformer raises an exception:

* The engine treats it as a **config error**:

  * Normalization for that table (and thus run) fails.
  * Artifact’s `run.status` -> `"failed"`, error recorded with script context.
  * Telemetry emits a `run_failed` or similar event.
* Best practice for config authors:

  * Fail fast with clear error messages when assumptions are violated.
  * Avoid catching and hiding exceptions unless truly recoverable.

---

## 5. Validation phase

Validators check **business rules** and produce structured issues. They also
live in `ade_config.column_detectors.<field_module>` and are optional.

### 5.1 Validator signature

Standard keyword-only signature:

```python
def validate(
    *,
    job,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_meta: dict | None,
    manifest: dict,
    env: dict | None,
    logger,
    **_,
) -> list[dict]:
    ...
```

Same parameters as `transform`, but:

* Focus is on reporting issues, not changing `row`.
* Validators are called **after** all transforms for the row have completed.

### 5.2 Validation issue model

Validators return a list of issue dicts, for example:

```python
return [
    {
        "code": "invalid_email_format",
        "severity": "error",
        "message": "Email must look like user@domain.tld",
        "details": {"value": value},
    }
]
```

Recommended keys:

* `code: str` (required)

  * Short, machine- and human-readable identifier.
  * e.g., `"missing_required"`, `"invalid_format"`, `"out_of_range"`.
* `severity: str` (required)

  * e.g., `"error"`, `"warning"`, `"info"`.
* `message: str` (required)

  * Human-friendly explanation, suitable for UI.
* `details: dict` (optional)

  * Arbitrary additional context for debugging or UI.

The engine wraps these into `ValidationIssue` objects, adding:

* `row_index: int` — original sheet row index.
* `field: str` — canonical field.

### 5.3 Validation ordering & scope

* For each row:

  * Transform phase completes first for all fields.
  * Then validators run for each field that defines a validator.
* Validators see the **final normalized row**:

  * They can validate both `value` and cross-field relationships via `row`.
* Cross-row constraints:

  * May be implemented using `state` to collect information across rows
    (e.g., track duplicates) and report issues during or after normalization.
  * For “summary” behavior, `on_run_end` hooks can also be used.

### 5.4 Exceptions in validators

If a validator raises an exception:

* Treated similarly to transformer errors:

  * Run is marked failed.
  * Error details recorded.
* Validators should not raise for normal “invalid data” cases:

  * Those are represented as issue dicts.
  * Exceptions should signal unexpected conditions in config code itself.

---

## 6. NormalizedTable structure

`NormalizedTable` captures the final output for a mapped table:

```python
@dataclass
class NormalizedTable:
    mapped: MappedTable
    rows: list[list[Any]]           # normalized matrix
    issues: list[ValidationIssue]   # all row-level issues
    output_sheet_name: str          # chosen by writer stage
```

### 6.1 Building `rows`

For each data row:

1. After transforms & validators:

   * Build a list of canonical values:

     ```python
     canonical_values = [
         row[field] for field in manifest.columns.order
         if column_meta[field].enabled
     ]
     ```

2. Append extra columns:

   ```python
   extra_values = []
   for extra in mapped.extras:
       col_idx = extra.index  # 0-based raw column index
       extra_values.append(
           mapped.raw.data_rows[row_offset][col_idx]
       )
   ```

3. Final row:

   ```python
   output_row = canonical_values + extra_values
   rows.append(output_row)
   ```

Invariants:

* All rows in a `NormalizedTable` have the **same length**.
* Canonical columns always appear in manifest order.
* Extra columns appear in `mapped.extras` order.

### 6.2 Aggregating issues

For each row:

* Collect all issue dicts returned by validators.
* Convert them into `ValidationIssue` objects, adding:

  * `row_index`
  * `field`
* Append them to `NormalizedTable.issues`.

Normalization does **not** decide whether issues are “fatal” or not; it only
records them. Policy decisions (e.g., “fail the job if any `severity="error"`”)
belong in the ADE backend or in hooks.

---

## 7. Artifact & telemetry integration

Normalization is tightly coupled with artifact and telemetry for observability.

### 7.1 Artifact (`artifact.json`)

During or after normalization, the artifact recorder (`ArtifactSink`) receives:

* For each table:

  * Validation issues: written under `tables[*].validation`.
* For each issue:

  * `row_index`, `field`, `code`, `severity`, `message`, `details`.

This provides a human/audit-friendly record of data quality for each run.

### 7.2 Telemetry events (`events.ndjson`)

`PipelineLogger` may also emit telemetry events during normalization, e.g.:

* `validation_issue`:

  * For each issue (or batch) with:

    * `field`, `code`, `row_index`, `severity`, plus file/sheet info.
* `normalization_stats`:

  * Summary counts of rows processed, issues per severity, etc.

The exact event set is flexible, but the pattern is:

* Telemetry → streaming / monitoring.
* Artifact → durable audit and reporting.

---

## 8. Guidance for config authors

### 8.1 Writing good transforms

* Prefer **pure, deterministic** transformations:

  * Same input row → same output row.
* Use `env` and `field_meta` rather than hard-coded constants:

  * Date formats, locales, thresholds, etc.
* Keep transforms **local** when possible:

  * Avoid cross-row dependencies unless you have a clear pattern using `state`.
* Avoid:

  * Network calls per row.
  * Unbounded in-memory structures (e.g., storing all rows in `state`).

### 8.2 Writing good validators

* Use validators to express **business rules**:

  * Required fields: `missing_required`.
  * Format: `invalid_format`.
  * Range checks: `out_of_range`.
* Return structured issue dicts rather than raising exceptions.
* Use `severity` consistently:

  * `error` for rules that should block acceptance.
  * `warning` for suspicious but tolerable situations.
* For cross-field checks:

  * Inspect the full `row` (e.g., “if `end_date` < `start_date`”).
* For cross-row checks:

  * Use `state` to accumulate and check after all rows are seen (or in a
    dedicated pass/hook).

### 8.3 Debugging

* Log via `logger.note(...)` and `logger.event(...)`:

  * Include `row_index`, `field`, and key details.
* Compare:

  * Input workbook → mapped headers (`artifact.mapping`) →
    normalized rows (`NormalizedTable.rows`) →
    validation issues (`artifact.validation`).

---

## 9. Edge cases & future extensions

Some known edge cases and potential future enhancements:

* **No data rows**:

  * A `MappedTable` may have a header but zero data rows.
  * Normalization should produce:

    * `rows = []`,
    * `issues = []`.
* **Completely unmapped tables**:

  * All columns become extras; canonical row has only `None` values.
  * Transform/validate may be skipped for fields with no mapping
    (depending on design choice).
* **Batch-level validation**:

  * Future enhancement:

    * Table-level or run-level validators that operate over entire `NormalizedTable`.
* **Additional outputs**:

  * Future: normalized data exported as CSV/Parquet while keeping current
    `NormalizedTable` and artifact contracts intact.

---

With these concepts and contracts in mind, you should be able to:

* Implement `pipeline/normalize.py` end-to-end, and
* Author robust, testable transform/validator scripts in `ade_config` that
  produce predictable, auditable normalized outputs.
# Column detectors

Column detectors are small, pluggable components that look at a single column of data and answer two questions:

1. **What kind of thing is this column?** (date, integer, currency, email, free text, …)
2. **How confident are we in that guess?**

This document explains:

* How column detection works conceptually
* What a detector is responsible for
* How scores are combined and resolved
* How to add or customize detectors

> Script API v3: detector functions must be keyword-only and declare both `logger`
> and `event_emitter` parameters (plus `**_` for future args).

---

## 1. What is a column detector?

A **column detector** is a function or object that:

* Receives:

  * The column header (name)
  * A sample of values from that column
  * Optional context (table name, other columns, locale, etc.)
* Returns a **detection result**, typically:

```text
DetectionResult:
  id:           unique identifier of the detector (string)
  label:        semantic type / role (e.g. "integer", "email", "id", "date")
  score:        confidence between 0.0 and 1.0
  metadata:     optional extra info (e.g. date format, enum values, min/max)
```

Detectors are **independent** of each other: each one only cares about whether *its own* pattern fits the column. A later aggregation step looks at all candidates and chooses the “winner” per column.

Typical consumers of column detectors:

* Type-casting and validation (e.g. parse strings into `Date` or `Decimal`)
* UI / formatting (date pickers, right-align numbers, show currency symbols)
* Data quality checks (e.g. “Primary key column has duplicates”)
* Auto-mapping / auto-joining tables

---

## 2. Detection pipeline overview

A typical detection run looks like this:

1. **Sampling**

   * Take the first *N* non-empty rows (or a stratified sample).
   * Normalize values (trim whitespace, unify null markers like `"NA"`, `"null"`, empty strings, etc.).

2. **Run detectors**

   * For each column, each registered detector is called once with the sample.
   * Each detector returns a `DetectionResult` (or “no match” / `null`).

3. **Aggregate scores**

   * Collect all `DetectionResult`s for a column.
   * Discard low-confidence candidates (below a global or per-detector threshold).
   * Choose the best one(s) according to score and tie‑breaking rules.

4. **Produce a column schema**
   For every column we end up with something like:

   ```text
   ColumnSchema:
     name:          "created_at"
     label:         "datetime"
     detector_id:   "datetime-iso-8601"
     confidence:    0.97
     metadata:
       format:      "YYYY-MM-DD HH:mm:ssZ"
       timezone:    "UTC"
   ```

5. **Downstream use**
   The schema is passed into parsing/validation, UI, or export logic.

---

## 3. Built‑in detector categories

The exact set of detectors depends on the host project, but they typically fall into these categories:

### 3.1 Primitive types

* **Integer / whole number detector**

  * Accepts values like `0`, `-12`, `42`, `"001"`.
  * Rejects floats (`1.5`), exponential notation, or mixed representations.
  * Often tracks min/max and whether negative values occur.

* **Float / decimal / numeric detector**

  * Accepts values like `1.5`, `3`, `1e-9`, `0.0001`.
  * Knows about locale-specific decimal separators when configured.
  * May record min, max, and whether all values are integers.

* **Boolean detector**

  * Accepts pairs like `true/false`, `yes/no`, `Y/N`, `1/0`.
  * Checks that **all** non-empty values fall into a small set of tokens.
  * Usually yields a high score when coverage is close to 100%.

### 3.2 Dates and times

* **Date detector**

  * Recognizes patterns like `2024-01-30`, `30/01/2024`, `Jan 30, 2024`.
  * Often tries multiple known formats and picks the best-fitting one.
  * Metadata typically includes the chosen format string.

* **Datetime / timestamp detector**

  * Similar to the date detector but includes time components.
  * Supports time zones (`Z`, `+01:00`, etc.) where configured.

### 3.3 Identifiers and keys

* **ID / primary key detector**

  * Looks for:

    * Very high uniqueness (distinct value ratio near 1.0)
    * No nulls
    * Stable patterns (e.g. UUIDs, numeric IDs of similar length)
  * Uses coverage + uniqueness as scoring factors.

* **Foreign key / reference-like detector**

  * Similar to ID but allows some duplicates and nulls.
  * Often combined with cross-table logic (outside the detector itself).

### 3.4 Text & categorical

* **Short categorical detector**

  * Few distinct values relative to total rows (e.g. `< 20 distinct values`).
  * Values are short (e.g. labels like `"Open"`, `"Closed"`, `"Pending"`).
  * Metadata often includes the full set of categories.

* **Free-text detector**

  * Default “catch-all” when other detectors fail.
  * Accepts long strings with spaces, punctuation, etc.
  * Score is often lower than a strong match from a more specific detector.

### 3.5 Pattern-based / semantic

* **Email detector**

  * Uses a robust regex for local-part + `@` + domain.
  * Checks that most values match and none are obviously impossible.

* **URL detector**

  * Accepts `http://`, `https://`, and sometimes bare domains.
  * Optionally validates hostnames and TLDs.

* **Phone number detector**

  * Looks for digit clusters, plus signs, parentheses, dashes/spaces.
  * May consider region/locale to refine patterns.

* **Geographic detectors**

  * Country codes, ISO region codes, postal codes, lat/long pairs, etc.

* **Currency detector**

  * Recognizes currency symbols (`$`, `€`, `£`) or ISO codes (`USD`, `EUR`).
  * Often built on top of the numeric detector (same values, extra semantics).

Your project may implement more specialized detectors (e.g. “Stock ticker”, “SKU”, “Tag list”), but they follow the same core ideas.

---

## 4. How scoring works

Each detector computes a **score** between `0.0` and `1.0`. While the exact formula is implementation-specific, it usually mixes these components:

* **Coverage**:
  Fraction of non-empty values that match the detector’s pattern.
  (Higher is better; e.g. `0.95` coverage means 95% of values matched.)

* **Consistency**:

  * Are formats stable? (e.g. all dates are `YYYY-MM-DD` vs. mixed formats)
  * Are lengths stable? (e.g. all phone numbers ~10–15 chars)

* **Conflict penalties**:

  * Many “almost matches” with outliers may reduce the score.
  * Values that clearly belong to another type (e.g. words inside a number column) decrease confidence.

* **Prior / specificity**:

  * More specific detectors (e.g. “email”) may get a slight boost when coverage is good.
  * Very generic detectors (like “free-text”) often have lower maximum scores.

A typical tie-breaking strategy:

1. Pick the result with the **highest score**.
2. If scores are similar (within a small epsilon), prefer the **more specific type** (e.g. “integer” over “numeric”, “email” over “text”).
3. As a fallback, keep the column as a **generic text** field instead of forcing a dubious specific type.

---

## 5. Configuration

The host application can expose configuration knobs for detection. Common options include:

### 5.1 Sampling

* `sample_size` – how many non-empty rows per column to inspect
* `max_rows` – hard cap on how many rows we scan in total
* `skip_header_rows` – if there are extra header lines before true data

Trade‑off: larger samples → better accuracy but slower detection.

### 5.2 Global thresholds

* `min_score` – discard detections below this score
* `min_coverage` – require that at least X% of non-empty values match
* `max_null_fraction` – treat columns with too many nulls as “unknown”

These thresholds can be tuned depending on how “risky” you want auto-detection to be.

### 5.3 Per-detector options

Each detector can also have its own parameters, for example:

* Date detector:

  * Allowed input formats
  * Default timezone
* Numeric detector:

  * Decimal separator
  * Grouping separator (`,` vs `.`)
* Categorical detector:

  * Maximum number of categories
  * Whether to capture category order

### 5.4 Enabling / disabling detectors

In some contexts you may want to:

* Disable expensive detectors (e.g. complex regex or machine-learning based ones)
* Disable types that aren’t useful in your domain (e.g. URL/phone if never expected)
* Force specific columns to a fixed type (bypassing detection entirely)

---

## 6. Writing a custom column detector

Custom detectors let you encode domain knowledge (e.g. “Employee ID”, “Order status”, “Project code”).

### 6.1 Minimal interface (conceptual)

In pseudocode, a detector typically looks like:

```text
Detector:
  id:      "my-detector-id"      # unique string
  label:   "semantic-type-name"  # what this detector recognizes

  detect(column_values, context) -> DetectionResult | null
```

Where:

* `column_values` is an iterable of normalized cell values from a single column.
* `context` may contain:

  * `column_name`
  * `row_count`
  * locale, hints, or global settings.

### 6.2 Recommended detection pattern

A robust detector tends to follow these steps:

1. **Pre-filter values**

   * Skip null/empty cells.
   * Maybe limit to a fixed sample size.

2. **Check basic constraints early**

   * e.g. for an “email” detector: require an `@` in almost all values.
   * If constraints are clearly violated, return `null` quickly.

3. **Validate and count matches**

   * Parse or regex-match each value.
   * Count:

     * how many values match
     * how many fail
   * Optionally collect metadata (min/max, distinct values, etc.).

4. **Compute score**
   Combine coverage and quality into a single `score` between `0` and `1`.

5. **Apply internal threshold**

   * If the score is too low, return `null` (no opinion).
   * Otherwise return a `DetectionResult` containing:

     * `id`
     * `label`
     * `score`
     * `metadata`

### 6.3 Best practices for custom detectors

* **Be conservative**
  It’s better to return `null` than to claim a column and be wrong.
  Err on the side of lower scores when unsure.

* **Handle edge cases**

  * Empty columns
  * Columns with only a single repeated value
  * Mixed-case or extra whitespace

* **Keep them fast**

  * Work on samples, not full tables, when possible.
  * Avoid heavy operations (e.g. network calls, complex ML) in basic detectors.

* **Make them deterministic**
  Given the same inputs, always produce the same output. This helps debugging and testing.

* **Log or expose explainability where possible**
  When debugging, it’s useful to know why a detector scored a column a certain way
  (e.g. “92% of values matched pattern X; 3 outliers ignored”).

---

## 7. Testing and debugging detectors

To keep detection robust over time:

* **Unit test each detector**

  * Positive examples (should match with high score)
  * Negative examples (should be rejected or low score)
  * Boundary cases (small samples, weird formatting)

* **Regression datasets**
  Maintain small CSV/TSV fixtures that cover typical datasets in your domain.
  Run the full detection pipeline on them and assert the resulting schema.

* **Debug output**
  When investigating mis-detections, it’s helpful if the system can show for a given column:

  * Which detectors fired
  * Their scores
  * Key metadata (coverage, matched formats, etc.)

This makes it much easier to adjust thresholds, refine patterns, or add new detectors.

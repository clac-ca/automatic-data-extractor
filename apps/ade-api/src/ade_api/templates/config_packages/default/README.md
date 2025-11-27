# ADE Config Package

This directory is an **ADE configuration package**.

The ADE engine reads Excel files and runs them through a pipeline:

1. It **detects tables and headers** in each sheet.
2. It **figures out which columns** map to the fields you care about.
3. (Optionally) **normalizes and validates** the data.
4. It **writes a cleaned workbook** and some artifacts.
5. (Optionally) calls **hooks** where you can log extra information or
   style the workbook.

This config package is where you describe **how** that should happen for your
use case.

You don’t need to know how the ADE engine is implemented.  
You just need to customize a few Python files that the engine calls at the
right time with the right information.

---

## 1. Layout

From the root of the config package you’ll see something like:

```text
pyproject.toml
README.md
src/
  ade_config/
    __init__.py
    manifest.json
    _shared.py
    row_detectors/
      header.py
      data.py
    column_detectors/
      member_id.py
      email.py
      first_name.py
      last_name.py
      ...
    hooks/
      on_run_start.py
      on_after_extract.py
      on_after_mapping.py
      on_before_save.py
      on_run_end.py
````

Very roughly:

* **`manifest.json`**
  Tells ADE which fields exist, which detector scripts to use, and which hooks
  to run. Think of it as the “config for the config package”.

* **`row_detectors/`**
  Functions that decide which rows are headers vs data.

* **`column_detectors/`**
  One file per field (e.g. `member_id`, `email`) that decides:

  * which column is that field,
  * how to clean the value,
  * how to validate it.

* **`hooks/`**
  Optional “extension points” that run at key steps in the pipeline
  (start of run, after tables are found, after mapping, before saving, at end).

Later, you can add a `docs/` folder next to this `README.md` for extra
configuration‑specific documentation. This `README` is meant to be edited and
kept in version control with the rest of the config.

---

## 2. The basic idea: ADE calls your functions

At a high level:

* ADE **reads Excel files**.
* At certain steps, it **calls functions in this package** and passes in
  information (rows, columns, tables, and a logger).
* Your function:

  * looks at the input,
  * applies your custom logic,
  * and **returns a value** that tells ADE what to do.

There are four main kinds of functions you’ll write:

1. **Row detection** – return a **score** saying “this looks like a header row”
   or “this looks like a data row”.
2. **Column detection** – return a **score** saying “this column looks like
   the field I care about”.
3. **Transform** – take a raw value and return a **cleaned value**.
4. **Validate** – check a value and return whether it is **valid or not**.

Hooks sit on the side and don’t control the pipeline.
They are **optional** and mostly used for logging, summary sheets, or small
touch‑ups.

---

## 3. Row detectors: finding headers and data rows

**Where:** `src/ade_config/row_detectors/`
**Start with:** `header.py` and `data.py`

When ADE is scanning a sheet, it doesn’t know yet which row is the header and
which rows are data. To help it, it calls your row detector functions.

### How it works

* ADE passes you:

  * the row index (position in the sheet),
  * the cell values in that row,
  * some extra context (run info, shared state, logger).
* You look at the row and **decide how strong it looks like a header or data**.
* You return a **score**: a number where a higher score means “more confident”.

You can have **as many detection functions as you want** in these files, as
long as their names start with `detect_`. ADE will call each one and use their
scores when deciding.

Example idea (simplified):

```python
def detect_header_row(row_index, row_values, **context):
    # Example rule: headers are usually near the top
    if row_index > 10:
        return 0.0  # unlikely to be a header

    # Example rule: headers often have more text than numbers
    text_like = sum(1 for v in row_values if isinstance(v, str) and v.strip())
    number_like = sum(1 for v in row_values if isinstance(v, (int, float)))

    if text_like == 0:
        return 0.0

    score = text_like / (text_like + number_like + 1)
    return score
```

In the real template files you’ll see the **full function signatures** with all
the context ADE passes in. You can copy those signatures and just change the
logic inside.

---

## 4. Column detectors: choosing and shaping columns

**Where:** `src/ade_config/column_detectors/`
**Start with:** `member_id.py` as the main example

Each file here is responsible for **one field** in your manifest (for example,
`member_id`, `email`, `first_name`).

For each field you can implement:

1. One or more **detection rules** (`detect_*`) to decide which physical
   column is that field.
2. An optional **transform function** to clean the raw value.
3. An optional **validate function** to enforce rules.

### 4.1 Detection: scoring how good a match a column is

When ADE is trying to match a field like `member_id`, it goes through each
column in the table and calls your `detect_*` functions from that field’s
module.

Each detection function:

* Receives information such as:

  * the cleaned header text (e.g. `"Member ID"`),
  * a small sample of values from the column,
  * the full column values,
  * the current table info,
  * and a logger.
* Runs your custom logic.
* Returns a **score** (a number where higher = better match).

You can define **multiple detect functions** per field:

```python
def detect_member_id_header_keywords(...):
    # look at header text, e.g. "member id", "customer id"
    return score

def detect_member_id_numeric_pattern(...):
    # look at values: mostly integers of reasonable length
    return score
```

As long as the function name starts with `detect_`, ADE will call it and use
your scores when choosing the best column.

### 4.2 Transform: clean up each value

Once ADE has decided which column is the `member_id` column, it will call your
**transform function** for each row.

The idea is simple:

* ADE passes you the **raw value** from that cell.
* You return the **cleaned value**.

Example (simplified):

```python
def transform_member_id(value, **context):
    if value is None:
        return None
    return str(value).strip()
```

You can also look at the rest of the row or manifest info if you need it
(the template shows the full signature).

### 4.3 Validate: check each value

After transform, ADE may call your **validate function**.

The idea:

* ADE passes you the cleaned value and information like:

  * field name,
  * row index,
  * whether the field is required.
* You decide whether the value is **acceptable**.
* You return something simple like `True`/`False` (the tmpl shows exact shape).

Example idea:

```python
def validate_member_id(value, field_meta, row_index, logger=None, **context):
    required = field_meta.get("required", False)

    if required and (value is None or value == ""):
        if logger is not None:
            logger.note(
                "validation_failed",
                field="member_id",
                row_index=row_index,
                reason="missing_required",
            )
        return False

    return True
```

You can log validation problems using the `logger` so they show up in the run
artifacts.

---

## 5. Hooks: optional extension points

**Where:** `src/ade_config/hooks/`

Hooks are **optional** functions that let you plug into key moments in the
pipeline without changing how detection and normalization work.

They are configured in `manifest.json` under a `"hooks"` section and loaded by
name, for example:

```jsonc
{
  "hooks": {
    "on_run_start": ["hooks.on_run_start"],
    "on_after_extract": ["hooks.on_after_extract"],
    "on_after_mapping": ["hooks.on_after_mapping"],
    "on_before_save": ["hooks.on_before_save"],
    "on_run_end": ["hooks.on_run_end"]
  }
}
```

Each hook module has a `run(...)` function. ADE calls that function and passes
in useful information like the current tables, the workbook, the run result,
and a logger.

You can think of each hook like:

* **`on_run_start`**
  “We’re about to start a run.”
  Good for logging run metadata or setting up shared state.

* **`on_after_extract`**
  “We’ve found some tables in the sheets.”
  Good for logging how many tables we found or dropping obvious junk tables.

* **`on_after_mapping`**
  “We’ve matched physical columns to fields.”
  Good for logging mapping summaries or fixing edge cases.

* **`on_before_save`**
  “We’ve built the normalized tables and workbook.”
  Good for styling the Excel file (freeze panes, add a summary sheet, etc.).

* **`on_run_end`**
  “The run is finished (success or failure).”
  Good for logging final status and metrics.

If you don’t need a hook, you can remove it from `manifest.json`.
If you do need one, you can copy the existing template and adjust the logic.

---

## 6. Using the logger

Most functions in this package receive a `logger` argument.
You can ignore it if you don’t need it, but it’s very handy for debugging and
telemetry.

The most common pattern is:

```python
if logger is not None:
    logger.note("short_human_message", **extra_details)
```

Where `extra_details` can be anything that helps you understand what happened
later, for example:

* `stage="column-detect"`
* `file="input.xlsx"`
* `sheet="Sheet1"`
* `field="member_id"`
* `row_index=42`
* `reason="missing_required"`

These notes are written to ADE’s event log (`events.ndjson`), so you can see
them when you inspect a run.

The template detectors and hooks all contain at least one `logger.note(...)`
call you can copy and adjust.

---

## 7. Rough picture of the “table” objects

You will see references to “tables” in hooks. You don’t need to know every
field, just the basics:

* **Extracted tables** (early stage, right after reading the sheet)
  Think: “what was in the Excel sheet, with header row + data rows”.

* **Mapped tables** (after column detection)
  Think: “which columns were matched to which fields, plus any extra columns”.

* **Normalized tables** (final stage)
  Think: “clean rows in the shape described by your manifest, plus any
  validation issues”.

The hook files in this template include small comment blocks that sketch the
exact fields you’ll typically use (file name, sheet name, rows, etc.).

---

## 8. Adding or changing behavior

Here are the most common things you’ll do when customizing this package:

### Add a new field

1. Add the field to `src/ade_config/manifest.json` (name, required, etc.).
2. Create a file in `src/ade_config/column_detectors/`
   (for example `department.py`).
3. Copy the structure from `member_id.py`:

   * add one or more `detect_department_*` functions,
   * add `transform_department` if you need to clean the value,
   * add `validate_department` if you need to enforce rules.

### Improve row detection

* Open `row_detectors/header.py` or `row_detectors/data.py`.
* Add extra functions whose names start with `detect_`, each implementing a
  small rule and returning a score.

### Style the output workbook

* Open `hooks/on_before_save.py`.
* Use the openpyxl APIs (as shown in the template) to:

  * freeze panes,
  * add filters,
  * create a summary sheet,
  * apply table styles.

---

## 9. Documentation inside this package

Because this `README.md` lives inside the config package, you can:

* Update it whenever you change behavior.
* Treat it as **versioned documentation** alongside the code.

If you need more detailed docs later, you can create a `docs/` folder next to
this file and add:

* `docs/row-detectors.md`
* `docs/column-detectors.md`
* `docs/hooks.md`
* `docs/logger.md`

…and link to them from this README.

---

If you’re new to this package, start by opening:

1. `src/ade_config/manifest.json` – to see what fields and hooks are defined.
2. `src/ade_config/column_detectors/member_id.py` – to see a full
   detect/transform/validate example.
3. `src/ade_config/hooks/on_before_save.py` – to see how hooks work.

From there, you can copy, rename, and adjust the existing code to fit your
data.
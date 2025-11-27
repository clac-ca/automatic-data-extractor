# ADE Config Package (Template)

This folder is a **template ADE configuration package**.

When ADE runs, it:

1. Opens your Excel file.
2. Finds tables and header rows.
3. Decides which column is which field (member ID, email, etc.).
4. Cleans and validates the values.
5. Writes a cleaned Excel file and some logs.

This config package is where you tell ADE **how your spreadsheets work**.

You don’t need to understand the ADE engine internals.  
You only need to edit a few Python files that ADE calls at the right times.

---

## 1. What’s in this package

Inside `src/ade_config/` you’ll see something like:

```text
manifest.json        # list of fields, their order, detectors, hooks, and other project settings
README.md            # this file – you can customize it as documentation for your config

row_detectors/
  header.py          # rules for finding the header row
  data.py            # rules for finding data rows

column_detectors/
  member_id.py       # full example for a single field
  email.py
  first_name.py
  last_name.py
  # add one file per field you want to extract

hooks/
  on_run_start.py
  on_after_extract.py
  on_after_mapping.py
  on_before_save.py
  on_run_end.py
````

---

## 2. How ADE uses this package

When you run ADE with this config package:

1. ADE reads each sheet in your Excel file.
2. It turns the sheet into a **table** (a header row plus data rows).
3. It calls your **row detector** functions to decide which row is the header and where data starts.
4. It calls your **column detector** functions to decide which Excel column is which field.
5. For each field and row:

   * it calls your **transform** function to clean the raw value,
   * then calls your **validate** function to check that the cleaned value is acceptable.
6. It writes out a new Excel file with cleaned, consistent data.
7. Along the way it may call your **hooks** (if you configure them) to log messages or style the workbook.

The engine passes information into your functions (rows, columns, run metadata, and a logger).
You write your own logic and return a result (score, cleaned value, pass/fail, etc.).

---

## 3. `manifest.json`: the “map” of your project

File: `src/ade_config/manifest.json`

The manifest is the central configuration file. It tells ADE:

* Which **fields** exist (for example `member_id`, `email`, `first_name`, `department`).
* The **order** in which those fields should appear in the output.
* Which **column detector script** should be used for each field
  (for example `column_detectors.member_id`).
* Which **hooks** to run at each lifecycle stage.
* Other project-level settings (for example, any thresholds or metadata the engine needs).

You can think of it as:

> “Here is the schema I care about, and here is which Python file handles each field and hook.”

When you add a new field that you want ADE to extract, you will:

1. Add it to `manifest.json`.
2. Create a matching file in `column_detectors/`.

---

## 4. Row detectors: deciding header vs data

Folder: `src/ade_config/row_detectors/`
Key files: `header.py`, `data.py`

Row detectors answer questions like:

* “Which row is the header row (with column names)?”
* “Which rows are actual data?”

### How row detection works

As ADE scans each sheet:

* It calls the functions in `row_detectors/header.py` and `row_detectors/data.py`.
* Each function is a **detection rule** for rows.
* A detection rule is just a small function whose name starts with `detect_`.

For each row, ADE passes your rule:

* The row index (position),
* The list of cell values in that row,
* Some extra context (run info, shared state, logger).

Your rule looks at that information and returns a **score**.

### Row scores: -1 to 1

Row detection uses a simple scoring idea:

* You return a number between **-1 and 1**.

  * `1`   → very strong signal that the row **matches** your rule
    (for example “this really looks like the header”).
  * `0`   → neutral (no strong opinion).
  * `-1`  → strong signal that the row is **not** what your rule looks for
    (for example “this is definitely not a header”).

You can have **as many `detect_...` functions as you want** in a row detector file:

* ADE calls all of them.
* Each one returns a score.
* ADE combines the scores to decide which row is the header and where data starts.

You don’t have to worry about how scores are combined; just focus on:

> “Given this row and context, how much should I push the probability up or down?”

---

## 5. Column detectors: fields, scores, transform, validate

Folder: `src/ade_config/column_detectors/`
Example: `member_id.py`

Each file in this folder typically handles **one field** from `manifest.json`.

For example:

* `member_id.py` handles the `member_id` field.
* `email.py` handles the `email` field.
* `first_name.py` handles `first_name`, etc.

You can create **as many column detector scripts as you want** – one for each field you want to extract from the spreadsheet.

Inside each file you usually define three kinds of functions:

1. **Detection rules** – functions whose names start with `detect_`.
2. A **transform function** – one per field.
3. A **validate function** – one per field.

### 5.1 Detection rules and scores

When ADE is trying to map fields to Excel columns, it:

1. Looks at every column in a table.
2. Calls your `detect_...` functions with:

   * the column header,
   * a sample of values,
   * the full column values,
   * and some context (run info, manifest, logger).

Each detection rule returns a score between **-1 and 1**:

* `1`  → very strong signal that the column **matches** a field.
* `0`  → neutral.
* `-1` → strong signal that the column is **not** that field.

**Important:**
Most of the time, a detection rule will only adjust the score for its own field.

* For example, in `member_id.py`, the main rule will increase or decrease the **member_id** score.

However, detection rules can also **adjust scores for other fields** if you want:

* Suppose a rule is sure a column is a `sid` number:

  * It can increase the score for the `sid` field.
  * At the same time, it can decrease scores for similar fields that should **not** be used (for example, `member_id`), to reduce false positives.

The template `member_id.py` shows how to structure these functions so it’s clear which field you’re scoring.

### 5.2 Transform: clean a single value

Once ADE has chosen which column represents a field, it goes row by row and calls the **transform** function for that field.

This is very simple:

* ADE passes in the **raw value** from the Excel cell (plus some context).
* Your function returns a **cleaned value**.

Example ideas:

* Trim spaces.
* Convert “ yes ” / “no” strings to `True` / `False`.
* Convert text like `"01/02/2024"` into a proper date.
* Normalize case (`"abc"` → `"ABC"`).

In words:

> Transform = “one value in, cleaned value out”.

ADE stores your cleaned value in the final table.

### 5.3 Validate: pass or fail a value

After transform, ADE calls the **validate** function for that field (if you define one).

* It passes the already cleaned value.
* You decide whether it is acceptable.

The simplest pattern is:

* Return `True` if the value is okay.
* Return `False` if it is not.

You can also use the provided logger inside validate functions to record what went wrong (missing, bad format, out of range, etc.), so you can see validation issues in logs later.

---

## 6. Hooks: optional extension points

Folder: `src/ade_config/hooks/`

Hooks are optional. Your config can work without them.

Hooks let you run extra code at certain moments in the run, for example:

* At the very start of the run (`on_run_start`),
* After tables are extracted from sheets (`on_after_extract`),
* After columns are mapped to fields (`on_after_mapping`),
* Before the workbook is saved (`on_before_save`),
* At the very end (`on_run_end`).

In each hook file:

* There is a `run(...)` function.
* ADE calls it and passes:

  * run information (IDs, metadata),
  * tables for that stage,
  * the workbook (for `on_before_save`),
  * and a logger.

Typical uses:

* Log run summaries or table statistics.
* Drop or reorder tables.
* Add a summary sheet to the output workbook.
* Apply formatting (freeze panes, table styles, etc.).

Hooks do **not** control the main detection logic; they just help you extend and polish what ADE already did.

---

## 7. The logger: writing useful notes

Most functions in this package receive a `logger` argument.

You can ignore it if you want, but it is very helpful for understanding what your rules are doing.

Common pattern:

```python
if logger is not None:
    logger.note(
        "short_message",
        key1=value1,
        key2=value2,
    )
```

Examples:

* In a column detector:

  ```python
  logger.note(
      "member_id_column_scored",
      field="member_id",
      header=header,
      score=score,
  )
  ```

* In a validate function:

  ```python
  logger.note(
      "validation_failed",
      field="member_id",
      row_index=row_index,
      reason="missing_required",
  )
  ```

These notes end up in ADE’s run logs so you can debug and monitor your config.

---

## 8. How to start customizing this template

If you’re building a new config from this template, a good starting path is:

1. **Update `manifest.json`**

   * List all the fields you care about.
   * Set the order you want them in the output.
   * Point each field at a matching `column_detectors/<field>.py` file.
   * Configure any hooks you want to enable.

2. **Add or edit column detector scripts**

   * Open `column_detectors/member_id.py` to see a complete example.
   * Copy it for each new field and adjust:

     * detection rules (`detect_*`),
     * transform function,
     * validate function.

3. **Tune row detection**

   * Open `row_detectors/header.py` and `row_detectors/data.py`.
   * Add or adjust `detect_*` functions to match how your header and data rows look.

4. **(Optional) Add hooks**

   * If you want custom summaries or formatting, open the files in `hooks/`.
   * `on_before_save.py` is a good place to start if you want to style the final Excel file.

---

### In short

* **Row detectors**: look at rows, return scores from **-1 to 1** about how likely they are to be header or data.
* **Column detectors**: look at columns for each field, return scores from **-1 to 1**; can also adjust scores for other fields to avoid false positives.
* **Transforms**: one value in, cleaned value out.
* **Validators**: cleaned value in, pass/fail out.
* **Hooks**: optional extras to log, adjust tables, or style the workbook.
* **`manifest.json`**: the master list of fields, their order, which scripts handle them, and which hooks to run.

Everything else is just filling in the rules that match how your spreadsheets are actually structured.
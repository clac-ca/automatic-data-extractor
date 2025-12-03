# Hooks

Hooks are **optional extension points** in your ADE config package.

They let you:

- log what happened during a run,
- inspect or tweak tables,
- style the final Excel workbook,
- add project‑specific behavior **without** changing the ADE engine.

This document explains:

- what hook stages exist,
- how to turn hooks on in `manifest.json`,
- what information your hook functions receive,
- and some practical examples you can copy.

> Script API v3: hooks must be keyword-only and include both `logger` and
> `event_emitter` keyword arguments (plus `**_` for future args).

You don’t have to be a Python expert.  
Think of hooks as **small functions that ADE calls at certain points**, passing you useful information.

---

## 1. When hooks run (stages)

During a run, ADE passes your data through several stages:

1. Read the Excel file, find tables and header rows.
2. Detect which column is which field (mapping).
3. Transform and validate the values (normalization).
4. Write the cleaned workbook.

Hooks can run **around** these stages:

| Stage              | When it runs                                       | Typical use cases                                      |
| ------------------ | -------------------------------------------------- | ------------------------------------------------------ |
| `on_run_start`     | Right after the run starts, before reading files   | Log run metadata, initialize counters/state.          |
| `on_after_extract` | After tables are found, before columns are mapped  | Log table summaries, drop obvious junk tables.        |
| `on_after_mapping` | After fields are matched to columns, before normalize | Log mapping summaries, fix edge‑case mappings.   |
| `on_before_save`   | After normalization, right before saving workbook  | Style the Excel file (freeze panes, add summary).     |
| `on_run_end`       | After everything finishes (success or failure)     | Log final status, duration, and output paths.         |

You can use **none**, some, or all of these.  
If a stage has no hooks configured, ADE just skips it.

---

## 2. Enabling hooks in `manifest.json`

Your hooks are wired up in `manifest.json` under the `"hooks"` section.

Example:

```jsonc
{
  "hooks": {
    "on_run_start":     ["hooks.on_run_start"],
    "on_after_extract": ["hooks.on_after_extract"],
    "on_after_mapping": ["hooks.on_after_mapping"],
    "on_before_save":   ["hooks.on_before_save"],
    "on_run_end":       ["hooks.on_run_end"]
  }
}
````

If you don’t want a hook to run, just remove its entry from `manifest.json`.

---

## 3. Hook function shape

Each hook module must define a `run(...)` function.

ADE calls it with **named arguments** (you don’t have to worry about the call itself).
A typical hook looks like this:

```python
def run(
    *,
    run=None,         # information about this run (ids, metadata)
    state=None,       # shared dict you can use across detectors/hooks
    manifest=None,    # settings from manifest.json
    tables=None,      # tables for this stage (may be None)
    workbook=None,    # Excel workbook (on_before_save only)
    result=None,      # final result info (on_run_end only)
    logger=None,      # logger object for notes
    stage=None,       # name of the hook stage (string)
    **kwargs,         # ignore any future extras
):
    ...
```

Important points:

* You can **ignore arguments you don’t need**.
* Some arguments will be `None` depending on the stage:

  * `tables` is only set for the “table” stages.
  * `workbook` is only set for `on_before_save`.
  * `result` is only set for `on_run_end`.
* You should **not** modify `run`, `manifest`, or `result` – treat them as read‑only.
* You **can** use and update `state` (it is shared across the whole run).

---

## 4. Returning values from hooks

For most hooks, you can either:

* **return nothing** (`None`)
  → ADE keeps using whatever it already has, or
* **return an updated object**
  → ADE uses your returned object for the rest of the pipeline.

Specifically:

* `on_after_extract`:

  * receives `tables` as a list of “extracted tables” (close to the raw sheet),
  * can return a **new list of tables** (for example, filtered or reordered).
* `on_after_mapping`:

  * receives `tables` as a list of “mapped tables” (columns matched to fields),
  * can return a **new list of tables** (for example, with adjusted mappings).
* `on_before_save`:

  * receives an Excel `workbook`,
  * can return the **workbook you want ADE to save** (often the same one after styling).

`on_run_start` and `on_run_end` usually just log notes and return nothing.

If you are not sure what to do, it is safe to:

* modify `tables` / `workbook` in place,
* and return `tables` or `workbook` at the end of your hook.

---

## 5. What “tables” look like (simple picture)

You will see a `tables` argument in some hooks.
You can think of them like this (simplified):

### 5.1 After extract: “extracted tables”

In `on_after_extract`, `tables` is a list of **extracted tables**:

* They come directly from the Excel sheets.
* Each contains:

  * source file,
  * sheet name,
  * header row,
  * data rows.

Use cases:

* Log how many rows each table has.
* Drop tables that are obviously empty or irrelevant.

### 5.2 After mapping: “mapped tables”

In `on_after_mapping`, `tables` is a list of **mapped tables**:

* The engine has already decided which column is which field.
* Each mapped table contains:

  * a reference back to its extracted table,
  * the column mappings (field → column),
  * any “extra” columns that weren’t mapped.

Use cases:

* Log which fields were mapped and which were missing.
* Adjust mapping for special cases (for example, move a field from one column to another).

### 5.3 Before save: “normalized tables”

In `on_before_save`, `tables` is a list of **normalized tables**:

* Each has:

  * rows in the shape defined by your manifest (fields + cleaned values),
  * a sheet name for the final workbook,
  * any validation issues.

At this point, the Excel `workbook` has already been built from these tables.
You normally use `tables` for summary information (counts, metrics) and `workbook`
to adjust formatting.

---

## 6. Using the logger inside hooks

Every hook receives an optional `logger` argument.

You can use it to record structured notes about what your hook is doing. The
most common method is:

```python
if logger is not None:
    logger.info(
        "short_message",
        key1=value1,
        key2=value2,
    )
```

Some useful fields you might pass:

* `stage` – the hook stage (e.g. `"on_after_extract"`).
* `file` – source file name.
* `sheet` – sheet/tab name.
* `table_index` – index of the table in that file.
* `reason` – short code for why something happened (`"dropped_empty_table"`, etc.).

These notes end up in ADE’s event log (`events.ndjson`) so you can review them
after a run.

---

## 7. Examples

### 7.1 `on_run_start`: log incoming run metadata

File: `src/ade_config/hooks/on_run_start.py`

```python
def run(*, run=None, logger=None, state=None, stage=None, **kwargs):
    """
    Called once at the very beginning of a run.

    Good for:
      - logging which config is being used,
      - recording input metadata,
      - initializing shared state in `state`.
    """
    if logger is None or run is None:
        return

    # example: record the run id and any custom metadata
    run_id = getattr(run, "run_id", None)
    metadata = getattr(run, "metadata", {}) or {}

    if state is not None:
        state["run_id"] = run_id

    logger.info(
        "run_started",
        stage=stage,
        run_id=run_id,
        metadata=metadata,
    )
```

---

### 7.2 `on_after_extract`: drop empty tables

File: `src/ade_config/hooks/on_after_extract.py`

```python
def run(*, tables=None, logger=None, stage=None, **kwargs):
    """
    Called after ADE has detected tables in the Excel file,
    but before it starts mapping columns to fields.

    `tables` is a list of extracted tables (file, sheet, header + rows).
    You may return a new list to keep/drop/reorder tables.
    """
    if tables is None:
        return None

    kept = []
    for t in tables:
        data_rows = getattr(t, "data_rows", []) or []
        source_file = getattr(getattr(t, "source_file", None), "name", None)
        source_sheet = getattr(t, "source_sheet", None)

        if data_rows:
            kept.append(t)
        else:
            if logger is not None:
                logger.info(
                    "dropped_empty_table",
                    stage=stage,
                    file=source_file,
                    sheet=source_sheet,
                )

    if logger is not None:
        logger.info(
            "extract_summary",
            stage=stage,
            total=len(tables),
            kept=len(kept),
        )

    return kept
```

---

### 7.3 `on_after_mapping`: summarize mappings

File: `src/ade_config/hooks/on_after_mapping.py`

```python
def run(*, tables=None, logger=None, stage=None, **kwargs):
    """
    Called after ADE has matched physical columns to fields,
    but before normalization.

    `tables` is a list of mapped tables (includes mapping info).
    """
    if tables is None or logger is None:
        return tables

    for mapped_table in tables:
        raw = getattr(mapped_table, "extracted", None)
        source_file = getattr(getattr(raw, "source_file", None), "name", None)
        source_sheet = getattr(raw, "source_sheet", None)

        mapping = getattr(mapped_table, "mapping", []) or []
        extras = getattr(mapped_table, "extras", []) or []

        logger.info(
            "mapped_table",
            stage=stage,
            file=source_file,
            sheet=source_sheet,
            mapped_columns=len(mapping),
            extra_columns=len(extras),
        )

    return tables
```

---

### 7.4 `on_before_save`: style the workbook

File: `src/ade_config/hooks/on_before_save.py`

```python
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

def run(*, workbook=None, tables=None, logger=None, stage=None, **kwargs):
    """
    Called after normalized tables have been converted into an Excel workbook,
    but before ADE saves it to disk.

    Use this to style the output: freeze panes, add tables, summary sheets, etc.
    """
    if workbook is None:
        return None

    sheet = workbook.active  # main normalized sheet
    sheet.freeze_panes = "A2"  # freeze header row

    # Turn the whole data region into an Excel "structured table"
    right = get_column_letter(sheet.max_column)
    table_ref = f"A1:{right}{sheet.max_row}"

    excel_table = Table(displayName="NormalizedData", ref=table_ref)
    excel_table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showRowStripes=True,
    )
    sheet.add_table(excel_table)

    if logger is not None:
        logger.info(
            "styled_workbook",
            stage=stage,
            sheet=sheet.title,
            rows=sheet.max_row,
            columns=sheet.max_column,
        )

    # Return the workbook we want ADE to save
    return workbook
```

---

### 7.5 `on_run_end`: log final status

File: `src/ade_config/hooks/on_run_end.py`

```python
def run(*, run=None, result=None, logger=None, stage=None, **kwargs):
    """
    Called once when the run has finished (success or failure).

    Use this to log the final status, duration, and outputs.
    """
    if logger is None or run is None or result is None:
        return

    run_id = getattr(run, "run_id", None)
    status = getattr(result, "status", None)
    output_paths = getattr(result, "output_paths", ()) or ()

    logger.info(
        "run_finished",
        stage=stage,
        run_id=run_id,
        status=status,
        outputs=[str(p) for p in output_paths],
    )
```

---

## 8. Summary

* Hooks are **optional** functions that run at well‑defined points in a run.
* You enable them in `manifest.json` under the `"hooks"` section.
* Each hook module provides a `run(...)` function that ADE calls with:

  * `run`, `state`, `manifest`, `tables`, `workbook`, `result`, `logger`, `stage`.
* Some hooks can return updated `tables` or `workbook` to change what happens next.
* Hooks are great for:

  * logging,
  * dropping or reordering tables,
  * fixing edge cases after mapping,
  * styling the final Excel output,
  * and emitting project‑specific metrics.

Start with the existing hook files in `src/ade_config/hooks/`, copy what you need,
and adjust the logic to match your project.

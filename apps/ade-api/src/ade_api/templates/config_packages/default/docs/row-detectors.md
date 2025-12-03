# Row detectors

Row detectors are the **first custom logic** ADE uses when it reads your Excel
sheets.

Their job is to answer very simple questions:

- “Which row is the **header** (the one with column names)?”
- “Which rows are **data** (actual records)?”
- “Which rows should be **ignored** (titles, notes, totals, etc.)?”

> Script API v3 requires row detectors to be keyword-only and accept both
> `logger` and `event_emitter` keyword arguments (plus `**_`).

You describe those rules in the files under:

```text
src/ade_config/row_detectors/
  header.py
  data.py
````

You don’t have to configure them in `manifest.json`.
The ADE engine looks into this folder and calls any functions that follow the
expected naming pattern.

---

## 1. How ADE calls your row detectors

When ADE reads a sheet:

1. It looks at each row one by one.
2. For each row, it calls the functions in `header.py` and `data.py` whose
   names start with `detect_`.
3. It passes each function:

   * the row’s position (`row_index`),
   * the list of cell values in that row (`row_values`),
   * and some extra context (run info, a shared `state` dictionary, a `logger`, and an `event_emitter`).

Your function:

* looks at the row and context,
* applies your own logic,
* and returns a **score between -1 and 1**.

ADE combines these scores across all your detection rules to decide:

* where the header row is, and
* where the data region starts.

You do **not** need to worry about the combining logic.
Just focus on returning a sensible score.

---

## 2. The scoring idea: -1 to 1

Row detection uses a simple, flexible scale:

* **`1`** → very strong signal that the row **matches** your rule
  (e.g. “this really looks like the header” or “this looks like a data row”).

* **`0`** → neutral. Your rule has no strong opinion.

* **`-1`** → very strong signal that the row **does not match** your rule
  (e.g. “this is definitely not a header/data row”).

You can think of each rule as “pushing” the decision up or down:

* Positive score → **push toward** “yes”.
* Negative score → **push away from** “yes”.
* Zero → **no push**.

ADE runs all your `detect_...` functions and uses the combined push to decide.

---

## 3. Multiple detection rules per file

You can define **as many detection rules as you want**, as long as their
names start with `detect_`.

For example in `header.py`:

```python
def detect_header_near_top(row_index, row_values, **context):
    # headers are usually near the top of the sheet
    return 1.0 if row_index < 5 else 0.0


def detect_header_has_most_text(row_index, row_values, **context):
    # header rows often have mostly text cells
    text_like = sum(1 for v in (row_values or []) if isinstance(v, str) and v.strip())
    number_like = sum(1 for v in (row_values or []) if isinstance(v, (int, float)))

    if text_like == 0 and number_like == 0:
        return 0.0

    if text_like > number_like:
        return 0.5  # weak positive
    return -0.5     # weak negative
```

And similarly in `data.py`:

```python
def detect_data_is_below_header(row_index, state, **context):
    header_row_index = state.get("header_row_index")
    if header_row_index is None:
        return 0.0
    return 0.8 if row_index > header_row_index else -0.8
```

**Key points:**

* All these `detect_...` functions run for each row.
* Each one returns a score between -1 and 1.
* ADE uses all of them when deciding header vs data.

You’re encouraged to keep each rule simple and focused on **one idea**.
It is often better to have several small rules than one huge, complex rule.

---

## 4. What arguments your functions receive

The exact arguments are shown in the template files, but conceptually you get:

* `run` – information about the current ADE run
  (run id, config id, metadata).

* `state` – a shared dictionary you can use to store counters or remember things
  (for example, the best header candidate you’ve seen so far).

* `row_index` – the position of the row in the sheet
  (usually zero-based: 0, 1, 2, …).

* `row_values` – a list of the cell values in that row
  (strings, numbers, dates, `None`, etc.).

* `logger` – an object you can use to write notes for debugging.

You don’t have to use all of these in every function.
The template signatures include them so they’re available if you need them.

---

## 5. Using the logger in row detectors

Every row detector function in the template accepts a `logger` argument.

You can ignore it, or use it like this:

```python
if logger is not None:
    logger.info(
        "row_scored_for_header",
        stage="row-detect",
        row_index=row_index,
        score=score,
    )
```

Typical fields you might record:

* `stage` – for example `"row-detect"`.
* `file` – the input file name (if available via `run` or `state`).
* `sheet` – the sheet/tab name.
* `row_index` – which row you are scoring.
* `reason` – a short code like `"too_few_text_cells"` or `"below_header"`.

These logs appear in ADE’s output artifacts so you can understand **why** a
row was or wasn’t chosen as a header or data.

---

## 6. Common pattern: header vs data

In this template:

* `row_detectors/header.py` focuses on **“is this row a header?”**
* `row_detectors/data.py` focuses on **“is this row a data row?”**

A common pattern is:

1. In `header.py`, write rules that:

   * strongly **favor** header-like rows,
   * strongly **penalize** rows that cannot be headers (too far down, empty, totals, etc.).

2. In `data.py`, write rules that:

   * favor rows that look like actual records (mostly data, consistent types),
   * penalize rows that are clearly decoration (titles, subheaders, notes).

The engine uses the combination of **header** and **data** scores to:

* pick a single header row, and
* identify where the data region begins.

---

## 7. Simple recipes

### 7.1 “First non-empty row is the header”

In `header.py`:

```python
def detect_header_first_non_empty(row_index, row_values, state=None, **context):
    # If we already saw a header candidate, stay neutral.
    if state and "header_row_index" in state:
        return 0.0

    # If this row has any non-empty values, treat it as a strong header candidate.
    has_values = any(v not in (None, "") for v in (row_values or []))
    if has_values:
        if state is not None:
            state["header_row_index"] = row_index
        return 1.0

    return 0.0
```

### 7.2 “Ignore the first N rows as decoration”

In `header.py` or `data.py`:

```python
DECORATION_ROWS = 2  # for example

def detect_ignore_top_rows(row_index, **context):
    if row_index < DECORATION_ROWS:
        return -1.0  # strongly argue against header/data
    return 0.0
```

---

## 8. How row detectors interact with the rest of the pipeline

Row detectors run **early** in the pipeline.

The decisions they help with affect everything that comes later:

* Column detectors assume headers are correctly identified.
* Transforms and validators operate on rows that were classified as data.

If headers are wrong, column detection becomes harder and you may see more
false positives or missing fields.

So it is worth spending a bit of time to:

* make your header and data rules reflect how your real sheets look, and
* log enough information (with `logger`) that you can understand why a run
  chose a particular header row or data start.

---

## 9. Where to go next

If you’re tuning row detectors:

1. Open `src/ade_config/row_detectors/header.py` and `data.py`.
2. Read the docstrings at the top of each file – they show the function
   signatures and give short examples.
3. Add or adjust `detect_...` functions to match the patterns you see in your
   spreadsheets.
4. Run ADE with sample files and inspect the run logs to see how your scores
   influenced the header and data selection.

Once header and data detection is working well, move on to:

* `docs/column-detectors.md` (for field-by-field column logic), and
* `docs/hooks.md` (for custom logging and workbook styling), if present.

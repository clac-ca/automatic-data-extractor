# Column Detectors

Column detectors decide which physical column should map to each manifest field.
In this template we demonstrate three straightforward fields:

* `first_name`
* `last_name`
* `email`

The examples are intentionally simple, readable, and easy to copy.

---

## Function Signature

Every detector function is keyword-only and receives a standard set of inputs:

```py
def detect_...(
    *,
    run=None,
    state=None,
    extracted_table=None,
    input_file_name: str | None = None,
    column_index: int | None = None,
    header: str | None = None,
    column_values: list[object] | None = None,
    column_values_sample: list[object] = (),
    manifest=None,
    logger=None,
    event_emitter=None,
    **_,   # required for forward compatibility
) -> float | dict:
    ...
```

### Arguments

| Argument                 | Purpose                                                     |
| ------------------------ | ----------------------------------------------------------- |
| **run/state**            | Run metadata and shared cache for this run.                 |
| **extracted_table**      | Full table context (header + data rows + source info).      |
| **input_file_name**      | Basename of the current source file.                        |
| **column_index**         | 1-based index of this column in the table.                  |
| **header**               | Cleaned column header text (string or `None`).              |
| **column_values_sample** | A small list of sample cell values from the column.         |
| **column_values**        | The full column values (already materialized once).         |
| **manifest**             | Manifest context for additional hints.                      |
| **logger**               | A standard `logging.Logger` for `debug/info/warning/error`. |
| **event_emitter**        | Structured event emitter (`event_emitter.custom(...)`).     |
| ******_                  | Required placeholder for future engine parameters.          |

All arguments are optional—detectors should behave gracefully when any are missing.

---

## Return Values

Detectors return **either**:

### 1. A float

A simple score applied **only to this field**.

```py
return 0.4
```

### 2. A dict of field → score adjustments

Used when a detector provides information about multiple fields at once.

```py
return {"first_name": 1.0, "last_name": -0.5}
```

You may omit fields you don't want to adjust.

### Scoring Concept

Think of each detector as adding **deltas**.
The engine:

1. Sums all deltas per field
2. Chooses the best-scoring column above threshold
3. Emits telemetry (`engine.detector.column.score`) automatically

You never need to emit scoring-related events manually—`event_emitter` is available for your own
`config.*` checkpoints when you want them (`event_emitter.custom("checkpoint", {...})`).

---

## Heuristics Used in This Template

The template detectors are intentionally readable—simple rules anyone can follow.

### **first_name.py**

* Headers containing “first”, “given”, or “fname” strongly indicate a first name column.
* Short, single-token values matching common first names increase the score.
* Full-name patterns (“Smith, John”, “John Smith”) reduce confidence.

### **last_name.py**

* Headers containing “last”, “surname”, “family”, or “lname” strongly indicate a surname column.
* Tidy single tokens or common surnames increase the score.
* Full names or email-like values reduce confidence.

### **email.py**

* Headers containing “email”, “e-mail”, “contact”, “login”, or “username” strongly indicate an email field.
* Multiple valid email-like values raise the score.
* Columns full of human names reduce the score.

---

## Transforms (Optional)

Each field module may also define:

```py
def transform(*, value, logger=None, event_emitter=None, **_):
    ...
```

Transforms normalize the **value**, not the mapping.
They return:

```py
{"email": normalized_value}
```

or

```py
None    # leave value unchanged
```

In this template, transforms simply normalize casing (title-case for names, lowercase for emails).

---

## Validators (Optional)

Fields may also define:

```py
def validate(*, value, logger=None, event_emitter=None, **_):
    ...
```

A validator returns a list of “issue” dictionaries, such as:

```py
[{"level": "error", "message": "email domain blocked"}]
```

This template does not include validators so the examples can stay focused on the detection and normalization basics—but hooks are fully supported if needed.

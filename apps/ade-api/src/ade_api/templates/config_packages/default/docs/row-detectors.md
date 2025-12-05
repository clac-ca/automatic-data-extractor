# Row Detectors

Row detectors determine which rows in a sheet are **headers**, which are **data**, and where each table begins and ends.
They run **once for every row** in every sheet, so they should be simple, fast, and focused.

---

## Location & Discovery

* Row detector files live in `ade_config/row_detectors/`.
* Any function named `detect_*` inside those modules will be called once per row.
* Multiple detectors can contribute: their scores are combined.

---

## Function Signature

Each detector function is keyword-only and receives the shape:

```py
def detect_...(
    *,
    row_index: int,             # 0-based index of the row
    row_values: list[object],   # raw cell values for the row
    logger=None,                # standard logging.Logger
    event_emitter=None,         # optional structured event emitter
    **_,                        # required for forward compatibility
) -> float | dict:
    return 0.8  # applies to this detector's default label (DEFAULT_LABEL)
    # or touch multiple labels explicitly:
    # return {"header": 0.8, "data": -0.2}
```

### Parameters

| Parameter         | Description                                         |
| ----------------- | --------------------------------------------------- |
| **row_index**     | 1-based index of the row being evaluated.           |
| **row_values**    | List of raw cell values for that row.               |
| **logger**        | Optional logger for debug/info output.              |
| **event_emitter** | Optional event emitter for custom telemetry.        |
| ******_           | Placeholder for future parameters (always include). |

---

## What to Return

Row detectors return either:

- A float, applied to the detector’s default label (set `DEFAULT_LABEL` in the module or via `detect_*.row_label`), or
- A dict of label → delta if you want to influence multiple labels explicitly.

These represent **deltas** added to the running total for each label. The legacy `"scores"` wrapper is no longer accepted.

Common labels:

* `"header"` — how header-like the row is
* `"data"` — how data-like the row is

You may include additional labels if your custom pipeline uses them, but `"header"` and `"data"` are the defaults the engine understands.

---

## How ADE Uses Row Detector Scores

1. All row detectors run on every row.
2. Their `header` and `data` deltas are **summed across detectors**.
3. ADE applies internal thresholds to decide:

   * Where a header row is
   * Where data starts
   * When tables end
4. After ADE identifies each table boundary, it automatically emits
   `engine.detector.row.score` events for debugging and telemetry.

You do not need to emit scoring events manually. Use the provided `event_emitter` only for your own
low-volume `config.*` checkpoints (`event_emitter.custom("checkpoint", {...})`).

---

## Template Detectors in This Workspace

Each template module sets `DEFAULT_LABEL` so a bare float return applies to the expected label.

### **header.py**

Heuristics include:

* Boosts `"header"` when the row appears early in the sheet
* Favors rows containing multiple string-like values
* Penalizes rows that look too numeric or too empty for a header

### **data.py**

Heuristics include:

* Boosts `"data"` for rows with mixed numbers and strings
* Penalizes all-empty or all-header-like rows
* Helps ADE distinguish actual data rows from decorative or spacer rows

These examples are intentionally simple and readable—ideal reference implementations for building your own detectors.

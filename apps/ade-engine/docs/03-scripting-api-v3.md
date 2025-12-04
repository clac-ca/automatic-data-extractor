# ADE Config Scripting (Script API v3)

> **Applies to:** `manifest.json` with `"script_api_version": 3`  
> **Audience:** config authors (`ade_config`) and engine contributors (`ade_engine`)

ADE runs your configuration code as a standard Python package named `ade_config`. Your scripts teach the engine how to:

1. **Find tables** (row detectors)
2. **Map columns** (column detectors)
3. **Transform values** (optional)
4. **Validate values** (optional)
5. **Write outputs** (engine + optional hooks)

Every callable receives two primitives:

- `logger` — normal `logging.Logger` for human-readable diagnostics
- `event_emitter` — structured telemetry via `event_emitter.custom("type_suffix", **payload)`

The engine already emits automatic score events (`run.row_detector.score`, `run.column_detector.score`), so you rarely need telemetry inside detectors.

---

## 0) Config package layout

```
ade_config/
  __init__.py
  manifest.json

  row_detectors/
    __init__.py
    header_and_data.py        # detect_* functions

  column_detectors/
    __init__.py
    email.py                  # detect_* + optional transform/validate
    first_name.py
    last_name.py

  hooks/
    __init__.py
    on_run_start.py           # run(...)
    on_after_extract.py
    on_after_mapping.py
    on_before_save.py
    on_run_end.py
```

Hook stage names are fixed: `on_run_start`, `on_after_extract`, `on_after_mapping`, `on_before_save`, `on_run_end`.

---

## 1) Script API v3 rules

All script functions must:

1. Use **keyword-only** arguments: `def run(*, ...)`
2. Accept `**_` for forward compatibility
3. Optionally accept any other kwargs you want; ADE will pass `logger` and `event_emitter` but you do not need to declare them explicitly.

If the signature isn’t keyword-only or doesn’t include `**_`, config loading fails early with a clear error.

---

## 2) Row detectors (table finding)

**Purpose:** vote on what each row represents (header, data, etc.). The engine aggregates label scores to decide header rows and data ranges.

**Location:** `ade_config/row_detectors/*.py`

**Discovery:** any callable named `detect_*` is executed per row.

**Signature:**

```py
def detect_something(
    *,
    run,
    state: dict,
    row_index: int,
    row_values: list,
    file_name: str | None,
    manifest,
    logger=None,
    event_emitter=None,
    **_,
) -> dict:
    return {"scores": {"header": <float_delta>, "data": <float_delta>}}
```

`file_name` is the basename of the current source file (useful when heuristics differ by feed/source).

**Return:** a dict with a `scores` mapping (label → delta). The engine sums deltas per label across detectors, then applies thresholds. Keep row detectors cheap—they run for every row.

---

## 3) Column detectors (column mapping)

**Purpose:** choose which physical column matches each manifest field. For each field and candidate column, the engine runs all `detect_*` functions in that field’s module and sums their deltas.

**Location:** `ade_config/column_detectors/<field>.py`

**Signature (detectors):**

```py
def detect_something(
    *,
    run,
    state: dict,
    extracted_table,
    file_name: str | None,
    column_index: int,            # 1-based
    header: str | None,
    column_values: list,
    column_values_sample: list,
    manifest,
    logger=None,
    event_emitter=None,
    **_,
) -> float | dict:
    ...
```

`extracted_table` is the `ExtractedTable` being scored (also exposed as `raw_table`/`unmapped_table` for backward compatibility).  
`file_name` is the current source file’s basename (also available via `extracted_table.source_file`). Use it for heuristics that depend on the input file without needing to parse the full path.

**Return:** either a float delta **or** a direct dict of deltas keyed by fields (no `"scores"` wrapper):

```py
return {"first_name": 1.0, "last_name": -0.5}          # direct mapping
return 0.4                                              # simple float delta
```

A float adjusts only the field being scored; a dict lets one detector influence multiple fields at once. The engine sums deltas per column, picks the best candidate above the mapping threshold, and emits `run.column_detector.score` with top candidates and contributions.

---

## 4) Transforms (normalization)

**Purpose:** clean/normalize values after mapping, per row per field.

**Location:** same module as the field detector.

**Signature:**

```py
def transform(
    *,
    run,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_config,
    manifest,
    logger=None,
    event_emitter=None,
    **_,
) -> dict | None:
    ...
```

**Return:** `None` (if you mutated `row` yourself) or a dict of updates merged into `row`.

---

## 5) Validation

**Purpose:** produce structured issues for auditing/UI. Runs after transforms.

**Signature:**

```py
def validate(
    *,
    run,
    state: dict,
    row_index: int,
    field_name: str,
    value,
    row: dict,
    field_config,
    manifest,
    logger=None,
    event_emitter=None,
    **_,
) -> list[dict] | None:
    ...
```

**Return:** list of issue dicts (`code`, `severity`, `message`, optional `details`). The engine aggregates and emits validation summaries.

---

## 6) Hooks (lifecycle customization)

**Stages:** `on_run_start`, `on_after_extract`, `on_after_mapping`, `on_before_save`, `on_run_end`.

**Location:** `ade_config/hooks/*.py`

**Signature:**

```py
def run(
    *,
    run,
    state: dict,
    file_names: tuple[str, ...] | None,
    manifest,
    tables=None,
    workbook=None,
    result=None,
    stage,
    logger=None,
    event_emitter=None,
    **_,
):
    ...
```

**Return:**

- `on_after_extract` / `on_after_mapping`: new list of tables or `None`
- `on_before_save`: a `Workbook` or `None`
- `on_run_start` / `on_run_end`: `None`

`file_names` contains the basenames of the files the run is working with (if known).

Use `logger` for human-readable notes; `event_emitter.custom(...)` for rare, structured milestones.

---

## 7) Event naming conventions (`event_emitter.custom`)

Keep event types discoverable:

- `hook.*` — hook milestones
- `transform.*` — rare transform anomalies
- `validation.*` — validation anomalies
- `domain.*` — domain-specific milestones

Avoid per-row custom events unless intentionally sampling—engine already emits summary score events.

---

## 8) Cheat sheet: when to use what

| Need                                        | Use                         |
| ------------------------------------------- | --------------------------- |
| Debug a heuristic or see interim scores     | `logger.debug(...)`         |
| Informational run progress                  | `logger.info(...)`          |
| Rare milestone in run timeline              | `event_emitter.custom(...)` |
| Explain mapping decisions                   | **Nothing** (engine emits)  |
| Explain table boundaries                    | **Nothing** (engine emits)  |
| Data quality reporting                      | validators (issues)         |

---

## Engine call-site references

- Row detectors: discovered/invoked in `core/pipeline/extract.py`.
- Column detectors: scored in `core/pipeline/mapping.py`.
- Transforms/validators: executed per row in `core/pipeline/normalize.py`.
- Hooks: wired via `config/hook_registry.py` and executed in `core/hooks.py`.

Use this doc as the source of truth for Script API v3 behavior.***

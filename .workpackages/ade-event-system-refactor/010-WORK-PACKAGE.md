> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [ ] Introduce the new **run-scoped** `logger` + `event_emitter` primitives (and remove `PipelineLogger` from config-facing surfaces)
* [ ] Thread `logger` + `event_emitter` through **every** engine pipeline stage and **every** ade-config callable (detectors/transforms/validators/hooks)
* [ ] Enforce **script_api_version=3** and update all signature validation to require `logger` + `event_emitter` (no backwards compatibility)
* [ ] Add **automatic** `run.column_detector.score` and `run.row_detector.score` events emitted by the engine (no changes required in detectors)
* [ ] Update all tests + fixtures to the new API and event shapes (including schema tests)
* [ ] Update all docs and rewrite config templates under `apps/ade-api/src/ade_api/templates` (include usage examples for both `logger` and `event_emitter`)

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Thread logger+event_emitter through mapping — abc123`

---

# Workpackage: Unify `logger` + `event_emitter` Across ADE Engine + ADE Config (Script API v3)

## 1. Objective

**Goal:**
Make the ADE experience instantly intuitive by standardizing two primitives everywhere:

* `logger`: standard Python `logging.Logger` for human-readable diagnostics (debug/info/warn/error)
* `event_emitter`: structured telemetry emitter for typed `run.*` events (including custom config events)

You will:

* Replace the current split where hooks receive a telemetry-specific logger and detectors receive a plain logger (today `execute_pipeline` passes the plain logger into extract/mapping/normalize, while hooks receive the telemetry logger). 
* Create a new Script API version (`script_api_version=3`) that requires all ade-config callables to accept `logger` and `event_emitter`.
* Add engine-generated events for detector scores so config authors don’t need to add telemetry calls inside each detector.
* Update all documentation and rewrite config templates in `apps/ade-api/src/ade_api/templates` to match the new API and include examples.

The result should:

* Provide **one consistent mental model**: “Use `logger` for logs, `event_emitter` for structured events.”
* Ensure every run produces a coherent telemetry stream including `run.started`, `run.phase.started`, `run.*.score`, `run.table.summary`, `run.completed`, plus any config-defined events.

---

## 2. Context (What you are starting from)

Today’s behavior is inconsistent and confusing:

1. **Two different “loggers” exist depending on where you are.**

* Pipeline stages call row/column detectors with a standard `logging.Logger` (e.g. mapping calls `detector(..., logger=logger)`), and that logger is constructed/fallback’d locally. 
* Hooks receive a different object (`PipelineLogger`) inside `HookContext.logger`. 
* `execute_pipeline` explicitly uses both: it passes the plain logger into extract/mapping/normalize/write, and passes the telemetry logger into hook stages. 

2. **Templates already demonstrate the confusing mismatch.**

* The default template README shows detectors/validators calling `logger.note(...)` (telemetry API), which does not match the current detector logger surface. 

3. **Row detectors are discovered dynamically and invoked per-row.**

* `extract_raw_tables` discovers `detect_*` functions under `ade_config/row_detectors/**` and scores every row. 

4. **Telemetry already exists and is robust—just not consistently available.**

* Telemetry envelopes and event types are emitted through `PipelineLogger` to `events.ndjson` with `run.event(...)`, `run.phase.started` via `pipeline_phase`, etc. 

**Hard constraints:**

* You explicitly do **not** want backwards compatibility: we will break old config signatures and old logger usage patterns.
* Templates and documentation must be updated as part of the same rollout.

---

## 3. Target architecture / structure (ideal)

**Summary:**

* `ade-engine` constructs **one** run-scoped `logger` and **one** run-scoped `event_emitter`.
* Those exact instances are passed through all engine layers and down into all ade-config callables.
* Engine emits score telemetry automatically: config code should not need to emit score events.

```text
apps/ade-engine/
  src/ade_engine/
    infra/
      telemetry.py                 # keep EventSink + NDJSON; replace PipelineLogger with EventEmitter (or rename)
      logging.py                   # NEW: TelemetryLogHandler + run-logger factory
    core/
      engine.py                    # builds run-scoped logger + event_emitter; enforces script_api_version=3
      pipeline/
        pipeline_runner.py         # threads both into all stages + hooks
        extract.py                 # passes both to row detectors; emits run.row_detector.score
        mapping.py                 # passes both to column detectors; emits run.column_detector.score
        normalize.py               # passes both to transforms/validators
        write.py                   # passes both to hooks on_before_save
      hooks.py                     # hooks take logger+event_emitter; no context/backcompat signature modes
    config/
      column_registry.py           # require logger+event_emitter in detect/transform/validate signatures
      hook_registry.py             # hook entrypoints require logger+event_emitter
    schemas/
      telemetry.py                 # add payload schemas for detector score events (optional but recommended)
  tests/
    fixtures/
      config_factories.py          # update generated temp ade_config to script_api_version=3 + new signatures
    pipeline/
      test_extract.py              # update + add detector score event assertions
      test_mapping.py              # update + add detector score event assertions
      test_normalize.py            # update signatures
    test_hooks.py                  # update signatures
    test_telemetry.py              # update event models + new event types
apps/ade-api/
  src/ade_api/templates/
    config_packages/
      default/                     # rewrite all templates to show logger + event_emitter usage
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Clarity:** Devs should immediately know: “logger = logs, event_emitter = telemetry events.”
* **Maintainability:** One Script API version (`v3`), enforced early with explicit, actionable errors.
* **Scalability:** New automatic score events must be **summary-style** (avoid per-row/per-detector floods by default).

---

### 4.2 Key components / modules

#### A) `EventEmitter` (structured telemetry)

**Location:** `ade_engine/infra/telemetry.py` (replace/rename `PipelineLogger`, which currently emits typed events) 

**Public surface (Script API v3):**

* `event_emitter.custom(type_suffix: str, **payload) -> None`
  Emits `run.<type_suffix>` events.
* `event_emitter.phase_started(phase: str, **payload) -> None`
  Emits `run.phase.started`.
* `event_emitter.table_summary(table: NormalizedTable) -> None`
  Emits `run.table.summary` (existing semantics).
* `event_emitter.validation_issue(...) / validation_summary(...) -> None`
  Emits validation events.

**Internal-only support:**

* `event_emitter.console_line(...)` *(optional internal)*: used by logging bridge to turn `logger.info(...)` into `console.line` events when desired.

#### B) `logger` (diagnostic logging)

**Location:** created per-run in `core/engine.py`.

* Might be a run-scoped `logging.LoggerAdapter` with run_id/config metadata attached.
* Uses normal Python logging handlers.
* Optionally includes a `TelemetryLogHandler` to also write `console.line` telemetry.

#### C) `TelemetryLogHandler` (logger → telemetry bridge)

**Location:** `ade_engine/infra/logging.py` (new)

Purpose:

* Make it so config authors can *only* write `logger.info(...)` and still see output surfaced in the run telemetry stream if the product/UI expects console lines.

---

### 4.3 Key flows / pipelines

#### Flow 1: Engine run setup

1. Load config runtime + manifest.
2. Validate `manifest.script_api_version == 3` (fail fast).
3. Build telemetry sink and run-scoped `event_emitter`.
4. Build run-scoped `logger` (optionally bridged to telemetry via `TelemetryLogHandler`).
5. Emit `run.started` via `event_emitter.custom("started", ...)`.
6. Execute pipeline phases, calling config logic with `(logger, event_emitter)` everywhere.
7. Emit `run.completed` via `event_emitter.custom("completed", ...)`.

(Engine currently emits `run.started` / `run.completed` using the telemetry logger) 

#### Flow 2: Extract (row detectors) + automatic row score event

During extract, the engine already:

* discovers row detectors from `ade_config/row_detectors/**`,
* scores rows,
* uses thresholding to open/close tables. 

**New behavior:**

* After each table is detected, emit `run.row_detector.score` as a **compact summary** event:

  * what row triggered the header,
  * thresholds,
  * the trigger row totals,
  * a small window of rows around it (optional, small),
  * and the final data row range.

This avoids generating one telemetry event per row.

#### Flow 3: Mapping (column detectors) + automatic column score event

Mapping already:

* runs all `detect_*` for each field against candidate columns,
* aggregates `ScoreContribution`s,
* chooses winners above threshold. 

**New behavior:**

* After scoring a field (per table), emit `run.column_detector.score` as a **compact summary** event:

  * the chosen column (or unmapped),
  * score + threshold,
  * and **top-N candidate snapshots** including contribution breakdown.

This gives deep explainability without detectors emitting events.

---

### 4.4 Open questions / decisions

* **Decision: Prefer compact summary score events (not per-row/per-detector events)**

  * Rationale: row detectors can run on tens of thousands of rows; per-row events would explode `events.ndjson`.
  * Summary events still give excellent debuggability and “why did it choose that?” insights.
* **Decision: Keep `event_emitter.custom()` as the only “free-form” method**

  * Rationale: it’s intuitive, avoids bikeshedding “emit vs event”, and matches your preference.

---

## 5. Implementation & notes for agents

### 5.1 Script API v3 (breaking change, no compatibility)

**Manifest**

* Update templates + docs to declare: `"script_api_version": 3`
* Add enforcement in engine run: if not 3, raise `ConfigError` with a clear message.

**Signature requirements**
Every ade-config callable must be keyword-only, accept `**_`, and include **both**:

* `logger`
* `event_emitter`

This applies to:

* Row detectors: `ade_config/row_detectors/**.py`
* Column detectors + transforms + validators: `ade_config/column_detectors/**.py`
* Hooks: `ade_config/hooks/**.py`

You will update the signature validation logic in:

* `core/pipeline/extract.py` for row detectors (today it already enforces keyword-only + `**_`). 
* `config/column_registry.py` for column detectors/transforms/validators (update its validator similarly). 
* `core/hooks.py` should be simplified to only call hooks via kwargs and to require `logger` + `event_emitter` (remove the “context positional” modes). 

---

### 5.2 EventEmitter implementation details

#### 5.2.1 Rename + API shape

In `ade_engine/infra/telemetry.py`:

* Rename `PipelineLogger` → `EventEmitter`
* Rename `.event(type_suffix, ...)` → `.custom(type_suffix, ...)`
* Keep existing typed helpers but rename for clarity:

  * `pipeline_phase(phase)` → `phase_started(phase)`
  * `record_table(table)` → `table_summary(table)`
  * Keep `validation_issue` / `validation_summary`

*(You can keep deprecated names internally for a commit or two while refactoring engine calls, but since you want no backwards compatibility, do not expose them as “supported.”)*

#### 5.2.2 Add detector score payload support (recommended)

In `ade_engine/schemas/telemetry.p y`, add Pydantic payload models for:

* `run.row_detector.score`
* `run.column_detector.score`

Even if you don’t strictly validate all payloads, this becomes living documentation and makes tests easy.

---

### 5.3 Logger setup (run-scoped + optional telemetry bridge)

Add `ade_engine/infra/logging.py`:

```python
import logging
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RunLogContext:
    run_id: str
    config_version: str | None = None

class TelemetryLogHandler(logging.Handler):
    """
    Bridges python logging -> console.line telemetry (optional).
    """
    def __init__(self, *, event_emitter, scope: str = "run"):
        super().__init__()
        self._event_emitter = event_emitter
        self._scope = scope

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            stream = "stderr" if record.levelno >= logging.WARNING else "stdout"
            # Internal-only console line, not part of config API.
            self._event_emitter.console_line(
                message=msg,
                level=level,
                stream=stream,
                scope=self._scope,
                logger=record.name,
                engine_timestamp=record.created,
            )
        except Exception:
            self.handleError(record)

def build_run_logger(*, base_name: str, event_emitter, bridge_to_telemetry: bool) -> logging.Logger:
    logger = logging.getLogger(base_name)
    logger.setLevel(logging.INFO)

    if bridge_to_telemetry:
        handler = TelemetryLogHandler(event_emitter=event_emitter)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger
```

**Why this matters:** Templates can simply do `logger.info("...")` and those messages can appear as console-like telemetry without reintroducing `note`.

---

### 5.4 Engine plumbing changes (thread everywhere)

#### 5.4.1 `core/engine.py`

* Build `event_emitter` from `TelemetryConfig.build_sink(...)` (already done today with `PipelineLogger`). 
* Build a run-scoped `logger` (and attach telemetry bridge if desired).
* Replace calls that currently use `pipeline_logger.event(...)` with `event_emitter.custom(...)`.
* Pass both `logger` and `event_emitter` into `execute_pipeline(...)`.

#### 5.4.2 `core/pipeline/pipeline_runner.py`

Change signature:

```python
def execute_pipeline(..., logger: logging.Logger, event_emitter: EventEmitter) -> PipelineOutputs:
```

* Replace `pipeline_logger.pipeline_phase(...)` with `event_emitter.phase_started(...)`
* Pass `event_emitter` into:

  * `extract_raw_tables(...)`
  * `map_extracted_tables(...)`
  * `normalize_table(...)`
  * `write_workbook(...)`
* Hooks: call `run_hooks(..., logger=logger, event_emitter=event_emitter, ...)` (instead of passing the telemetry object as logger). Today hooks receive `PipelineLogger` via `logger=`. 

#### 5.4.3 `core/pipeline/extract.py`

* Add `event_emitter` param to `extract_raw_tables(...)`.

* When calling row detectors, pass:

  * `logger=logger`
  * `event_emitter=event_emitter`

* Emit `run.row_detector.score` summary events **per extracted table**.

**Implementation approach for row score summary event**

* Keep current table detection logic.
* When a table is closed/created, compute a *small* payload:

  * Provide header row index, data row range, thresholds.
  * Re-run row detectors for the header row only to compute detector-level contributions (cheap and avoids storing per-row contributions).

#### 5.4.4 `core/pipeline/mapping.py`

* Add `event_emitter` param to `map_extracted_tables(...)` and `_score_field(...)`.
* Pass `event_emitter=event_emitter` into every detector call.
* Emit `run.column_detector.score` summary per field per table:

  * include chosen column (or unmapped),
  * include top-N candidate breakdown (including contributions).

**Implementation approach for top-N candidates**

* While scoring candidates, keep `(score, candidate_meta, contributions)` for each.
* After scoring, sort descending by score and slice to N (recommend `N=3`).
* Chosen candidate is the same logic as mapping winner logic and should be included in the top-N payload even if below threshold.

#### 5.4.5 `core/pipeline/normalize.py`

* Add `event_emitter` param to `normalize_table(...)`.
* Pass `event_emitter` into `transformer(...)` and `validator(...)`.

#### 5.4.6 `core/hooks.py` + `config/hook_registry.py`

* Replace `HookContext.logger: PipelineLogger` with:

  * `logger: logging.Logger`
  * `event_emitter: EventEmitter`
* Remove “positional context” invocation rules; always do kwargs and require `logger` + `event_emitter`.
* Keep return semantics:

  * after-extract / after-mapping hooks can return replacement tables
  * before-save can return replacement workbook

---

### 5.5 Engine-emitted detector score events (new)

#### Event: `run.column_detector.score`

**When:** after scoring a field (during mapping)
**Payload shape (recommended):**

* `source_file`, `source_sheet`, `table_index`
* `field`
* `threshold`
* `chosen`: `{ column_index (1-based), source_column_index (0-based), header, score, passed_threshold }` (or `None`/`-1` for unmapped)
* `candidates`: list of up to N entries, each:

  * column index info + header
  * `score`
  * `contributions`: list of `{ detector, delta }`

#### Event: `run.row_detector.score`

**When:** after an extracted table is found (during extract)
**Payload shape (recommended):**

* `source_file`, `source_sheet`, `table_index`
* `thresholds`: `{ header, data }`
* `header_row_index`
* `data_row_start_index`, `data_row_end_index`
* `trigger`:

  * `row_index`, `header_score`, `data_score`
  * `contributions`: list of `{ detector, scores: {header?: float, data?: float} }`
  * `sample`: first ~5 cell values from the trigger row (optional)

---

### 5.6 Config author examples (new API, to use in templates + docs)

#### A) Column detector (no need to emit score events manually)

```python
def detect_email_header(
    *,
    header: str | None,
    column_values_sample: list[object],
    logger,
    event_emitter,
    **_,
) -> float:
    """
    Column detector: return a score contribution (delta).
    Engine will automatically emit run.column_detector.score summaries
    so you generally do NOT need to emit score telemetry here.
    """
    score = 0.0

    if header and "email" in header.lower():
        score += 0.8

    # Use logger for diagnosis
    logger.debug("detect_email_header header=%r score=%.2f", header, score)

    # Use event_emitter for rare, structured domain events (optional)
    if header and "e-mail" in header.lower():
        event_emitter.custom(
            "detector.nonstandard_header",
            field="email",
            header=header,
            note="Header uses 'e-mail' spelling",
        )

    return score
```

#### B) Row detector (still just returns score deltas)

```python
def detect_probable_header_row(
    *,
    row_index: int,
    row_values: list[object],
    logger,
    event_emitter,
    **_,
) -> dict:
    """
    Row detector: returns per-label score contributions.
    Engine will emit run.row_detector.score summaries (table-level),
    so keep this focused on scoring logic.
    """
    header_delta = 0.0

    # Simple heuristic: early rows with many strings look like headers
    if row_index <= 5:
        strings = sum(1 for v in row_values[:10] if isinstance(v, str) and v.strip())
        if strings >= 3:
            header_delta = 0.6

    logger.debug("row=%d header_delta=%.2f sample=%r", row_index, header_delta, row_values[:5])

    return {"scores": {"header": header_delta}}
```

#### C) Transform

```python
def transform_member_id(
    *,
    value,
    row_index: int,
    logger,
    event_emitter,
    **_,
) -> dict:
    """
    Transform functions should normalize raw values into canonical output.
    """
    if value is None:
        logger.warning("member_id missing at row=%d", row_index)
        event_emitter.custom("transform.missing_value", field="member_id", row_index=row_index)
        return {"member_id": None}

    cleaned = str(value).strip().upper()
    return {"member_id": cleaned}
```

#### D) Hook (lifecycle customization)

```python
def run(
    *,
    stage,
    tables=None,
    workbook=None,
    result=None,
    logger,
    event_emitter,
    **_,
):
    """
    Hooks get the same logger + event_emitter primitives, consistently.
    """
    logger.info("Hook stage=%s tables=%s", stage.value, len(tables or []))

    event_emitter.custom(
        "hook.checkpoint",
        stage=stage.value,
        tables=len(tables or []),
        status="ok",
    )

    # Optionally mutate pipeline outputs depending on stage:
    if stage.value == "on_after_mapping" and tables:
        return tables  # or a modified list
```

---

### 5.7 Tests & fixtures updates

You must update:

* `tests/fixtures/config_factories.py` to generate ade_config packages with:

  * `script_api_version: 3`
  * detectors/hooks/transforms/validators that accept `logger` + `event_emitter`
* All pipeline tests to accept breaking API change.
* Add tests asserting:

  * `run.column_detector.score` events exist and have expected shape for a simple mapping case
  * `run.row_detector.score` events exist and reflect detected header row
  * hooks now receive the plain logger + event_emitter and can emit custom events

Because `events.ndjson` is treated as a contract, add/adjust schema tests accordingly. 

---

### 5.8 Docs + template rewrite (required final step)

**Docs to update (minimum):**

* `apps/ade-engine/docs/02-config-and-manifest.md` (script_api_version bump guidance; mention v3 contract)
* `apps/ade-engine/docs/07-telemetry-events.md` (new event types + event_emitter naming)
* `apps/ade-engine/docs/08-hooks-and-extensibility.md` (new hook signature + logger/event_emitter)
* Any other docs that mention `PipelineLogger` or `logger.note`

**Templates to rewrite (required):**

* `apps/ade-api/src/ade_api/templates/config_packages/default/**`

  * Update manifest to `"script_api_version": 3`
  * Replace `logger.note(...)` usage with `logger.info(...)`
  * Add at least one example `event_emitter.custom(...)` in:

    * a column detector
    * a hook
  * Add short explanation comments: “logger is for logs; event_emitter is for structured run events.”

(Templates currently reference `logger.note` heavily, so this step is non-optional.) 

---

### 5.9 Performance / safety notes

* Do **not** emit per-row or per-detector telemetry events by default; the chosen design emits **summary** events per extracted table and per field mapping.
* Keep summary payloads bounded (top-N candidates; short value samples).
* Ensure no sensitive raw data is dumped into telemetry by default; keep samples short and consider redacting if needed later.

---

### 5.10 Deliverables

By the end, we should have:

1. Script API v3 enforced and documented.
2. `logger` + `event_emitter` passed consistently to:

   * row detectors, column detectors, transforms, validators, hooks
3. Engine emits two new automatic score events:

   * `run.row_detector.score`
   * `run.column_detector.score`
4. All tests green.
5. All docs updated.
6. ade-api config templates rewritten with clear examples for both primitives.

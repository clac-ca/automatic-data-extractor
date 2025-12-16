> **Agent instruction (read first):**
>
> - Treat this work package as the **single source of truth** for this task.
> - Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks.
> - Prefer small, incremental commits aligned to checklist items.
> - If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

- [x] Finalize schema v1 contract, invariants, naming conventions, and examples
- [x] Align docs to strict validation + stable semantics (outputs, rollups, evaluation)
- [ ] Refactor `ade_engine.models.events` payloads to consistent `*V1` + `schema_version=1` (breaking; no backwards compatibility)
- [ ] Define Pydantic v2 models for `engine.run.completed` in `ade_engine.models.events` and register schema
- [ ] Implement `RunCompletionReportBuilder` (incremental accumulation + rollups + grading)
- [ ] Instrument pipeline to capture facts needed for summaries (scan stats, regions, mapping diagnostics, outputs)
- [ ] Emit `engine.run.completed` exactly once per run (always, even on failure)
- [ ] Add/adjust tests (schema validation, invariants, “failed run still summarizes progress”)

---

# Implement authoritative run summary event (`engine.run.completed`)

## 1. Objective

Make `engine.run.completed` the authoritative evaluation report for an ADE run:

- not just “finished/failed”
- but **how successful ADE was at understanding the input**, and why

This summary is distinct from step-by-step logs:

- Step logs explain *what happened during processing*.
- The summary explains *what ADE believes the structure is*, *how complete/confident that belief is*, and *what limited/blocked success*.

**Hard requirement:** Emit the run summary **exactly once per run**, even when the run fails mid-way (partial progress preserved).

---

## 2. Scope / assumptions

**Target:** post-refactor ADE Engine layout from `.workpackages/ade-engine-folder-restructure`
(`cli/`, `application/`, `models/`, `extensions/`, `infrastructure/`). Update paths if using older layout.

**Backwards compatibility:** not required. This work package may introduce breaking changes to enforce:

- consistent versioning (`schema_version=1` as an **int major**)
- consistent naming (`*V1` suffix)
- strict payload validation (`extra="forbid"` + `strict=True`)

---

## 3. Decisions (schema v1) — single source of truth

### 3.1 Event identity and naming

- **Schema identity (registry key):** `engine.run.completed`
- **Emit call (engine logger context):** `logger.event("run.completed", ...)`
  - Engine logger qualifies `run.completed` → `engine.run.completed`.
- If emitting from a non-engine logger context, emit the fully-qualified name:
  `logger.event("engine.run.completed", ...)`

### 3.2 Versioning

- Payload includes `schema_version` only.
- `schema_version` is an int major. For v1: `schema_version=1`.

### 3.3 Strict validation / type choices

Because the engine validates with `model_validate(..., strict=True)`:

- `execution.duration_ms` is an int (non-negative).
- Scores are floats; ensure producers cast to float before emitting.
- Prefer `model_dump(exclude_none=True)` for compact payloads.

### 3.4 Mapping semantics (column → field)

Each physical column has a `mapping.status`:

- `mapped`
  - `field`, `score`, `method` required
  - `unmapped_reason` absent
- `ambiguous`
  - no selected `field/score/method`
  - non-empty `candidates`
  - `unmapped_reason` required
- `unmapped`
  - no selected `field/score/method`
  - `unmapped_reason` required
  - candidates optional
- `passthrough`
  - no selected `field/score/method`
  - `unmapped_reason` must be `passthrough_policy`
  - candidates optional

**Reason codes (stable enum):**

- `no_signal`
- `below_threshold`
- `ambiguous_top_candidates`
- `duplicate_field`
- `empty_or_placeholder_header`
- `passthrough_policy`

### 3.5 Candidate cap

- Emit top-N candidates per column.
- v1: `MAX_CANDIDATES = 3`
- Candidates are sorted by descending score.

### 3.6 Payload size policy (v1)

- Per-column mapping lives at **table scope** under `structure.columns[*].mapping`.
- Field-centric summaries (`fields[]`) exist at **run scope only**.
- Lower scopes provide `counts` and `validation` rollups (+ optional scan/outputs).

### 3.7 Execution vs evaluation blocks

- `execution` and `evaluation` appear at **run scope only**.
- Lower scopes do not carry independent `execution/evaluation`.

### 3.8 Outputs semantics (v1)

- `outputs.normalized` is included **only when an output artifact is actually written**.
- If output writing fails, outputs pointers must be omitted (avoid misleading consumers).

### 3.9 Indexing conventions

- workbook/sheet/table indexes are **0-based**
- `row_start` in `structure.header` and `structure.data` is **1-based** (spreadsheet row numbers)

---

## 4. Target architecture / structure

### 4.1 High level

- A `RunCompletionReportBuilder` accumulates table summaries as the pipeline progresses.
- Builder rolls up table summaries into sheet/workbook/run summaries deterministically.
- `Engine.run()` emits `engine.run.completed` in a `finally` path so failures still produce summaries.

Tables are the ground truth; higher levels are rollups.

### 4.2 Files / modules (expected)

```text
apps/ade-engine/src/ade_engine/
  models/events.py                        # versioned payload models (RunCompletedPayloadV1, etc.)
  models/table.py                         # region/output_range/mapping diagnostics on TableData
  application/run_completion_report.py    # RunCompletionReportBuilder + rollup/grading logic
  application/engine.py                   # create builder; emit run.completed in all cases
  application/pipeline/pipeline.py        # capture scan stats; call builder per table/sheet
  application/pipeline/render.py          # attach output_range to TableData
  application/pipeline/detect_rows.py     # ensure region metadata is accessible for summaries
  application/pipeline/detect_columns.py  # expose mapping diagnostics (candidates + unmapped reason)
  infrastructure/observability/logger.py  # emit engine.run.completed via engine logger namespace
```

---

## 5. Summary schema (v1) — contract overview

Hierarchy:

- run
  - workbooks[]
    - sheets[]
      - tables[]

Run-level fields:

- `schema_version=1`
- `scope="run"`
- `execution` (status, timestamps, duration, optional failure)
- `evaluation` (outcome + findings)
- `counts` (rollups)
- `validation` (rollups)
- `fields[]` (run-only field rollup)
- `outputs` (optional, only when written)
- `workbooks[]`

Workbook fields:

- `scope="workbook"`
- `locator`
- `counts`
- `validation`
- `sheets[]`

Sheet fields:

- `scope="sheet"`
- `locator`
- `counts`
- `validation`
- `scan` (optional)
- `tables[]`

Table fields:

- `scope="table"`
- `locator`
- `counts`
- `validation`
- `structure` (region/header/data/columns)
- `outputs` (optional, only when written)

---

## 6. Instrumentation flows (what must be captured)

### Flow A — Per-sheet scan (optional)

Record sheet scan stats from row materialization:

- `rows_emitted`
- `stopped_early`
- `truncated_rows`

### Flow B — Per-table summary

For each detected table region, capture:

- region bounds (A1 range)
- header info (row start/count, inferred flag)
- data info (row start/count)
- physical columns (index, header raw/normalized, non-empty cell count)
- per-column mapping decision:
  - status, selected field/score/method (if mapped)
  - top-N candidates (field/score)
  - unmapped_reason for ambiguous/unmapped/passthrough
- validation rollups
- output range after render (only if output is written)

### Flow C — Rollups + grading

- Roll up deterministic sums across tables → sheets → workbooks → run.
- Compute `evaluation.outcome` + `evaluation.findings` from rollups (see `supporting-docs.md`).

### Flow D — Emit once

- Emit `engine.run.completed` exactly once even on failure, capturing partial progress.

---

## 7. Operational policy

### 7.1 Log level / persistence

`engine.run.completed` must be persistable regardless of CLI console verbosity.

- Emit at `INFO`.
- Ensure structured event sinks are not suppressed by `--quiet` console settings.

---

## 8. Supporting docs

See:

- `supporting-docs.md` — rationale + semantics
- `pydantic.md` — strict Pydantic v2 model contract (schema v1)
- `examples/` — minimal, compact JSON examples (aligned with `exclude_none=True`)

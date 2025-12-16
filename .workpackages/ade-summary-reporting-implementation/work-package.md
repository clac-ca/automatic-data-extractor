---
> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.
---

## Work Package Checklist

- [ ] Finalize `engine.run.completed` summary contract v{{SCHEMA_VERSION}} and document invariants — {{STATUS}}
- [ ] Add Pydantic v2 models for summary payload(s) and register schema in `ENGINE_EVENT_SCHEMAS` — {{STATUS}}
- [ ] Implement `RunSummaryBuilder` (incremental accumulation + rollups + grading) — {{STATUS}}
- [ ] Instrument pipeline to capture the facts needed for summaries (sheet scan stats, table regions, mapping decisions, output range) — {{STATUS}}
- [ ] Emit `engine.run.completed` exactly once per run (always, even on failure) — {{STATUS}}
- [ ] Add/adjust tests (schema validation, invariants, “failed-run still summarizes progress”) — {{STATUS}}
- [ ] Update docs/readme snippets for event consumers (ade-api persistence expectations) — {{STATUS}}

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, e.g.:
> `- [x] Add Pydantic models — 3f1a9c2`

---

# Implement authoritative run summary event (`engine.run.completed`)

## 1. Objective

**Goal:**
Make `engine.run.completed` the **authoritative evaluation report** for an ADE run: not just “finished/failed”, but **how successful ADE was at understanding the input** and why.

You will:

- Define a **strict, versioned** payload schema (`schema_version` only) for `engine.run.completed`.
- Generate a **hierarchical summary**: `run → workbooks → sheets → tables`.
- Ensure summary answers:
  - what table structure ADE inferred
  - what columns/fields were mapped vs unmapped/ambiguous/empty
  - how emptiness/sparsity and scan limits affected what was processed
  - validation issue rollups
- Emit `engine.run.completed` **exactly once**, even if the run fails mid-way (partial progress preserved).

The result should:

- Be consistent, minimal, and standard (snake_case, intentional naming).
- Be machine-friendly (counts, stable reason codes) and human-friendly (structure/mapping detail).
- Be suitable for `ade-api` to persist as the canonical run summary.

**Supporting docs:**
- [supporting-docs.md](supporting-docs.md)
- [pydantic_v2.md](pydantic_v2.md)

---

## 2. Context (What you are starting from)

Today:

- `ade_engine/logging.py` provides a structured logging envelope plus a strict schema registry for `engine.*` events.
- `engine.run.completed` exists but is currently a thin “footer” (status + timestamps + output path) and does **not** measure extraction success.
- The pipeline already computes the key facts we need (table regions, physical columns, mapping decisions, issues, output ranges), but they are not consistently retained for summary rollups.

Constraint:

- The run summary must be produced from **engine state**, not by scraping logs (log level filtering and failures would make that unreliable).

---

## 3. Target architecture / structure (ideal)

### 3.1 High-level

- A `RunSummaryBuilder` accumulates **table summaries** as the pipeline progresses.
- Builder rolls up table summaries into sheet/workbook/run summaries deterministically.
- At run completion (success or failure), the engine emits:
  - `engine.run.completed` with `data=<RunSummaryPayloadV1>`

### 3.2 Files / modules (expected)

```text
apps/ade-engine/src/ade_engine/
  logging.py                      # register new strict schema for engine.run.completed
  summary_schema.py               # Pydantic v2 models for summary payload
  summary_builder.py              # RunSummaryBuilder + rollup/grading logic
  engine.py                       # create builder; emit run.completed in all cases
  pipeline/pipeline.py            # capture scan stats; call builder per table/sheet
  pipeline/render.py              # attach output_range to TableData
  pipeline/detect_rows.py         # ensure region metadata is accessible for summaries
  pipeline/detect_columns.py      # expose mapping diagnostics (candidates + unmapped reasons)
  pipeline/models.py              # store region/output_range/mapping diagnostics on TableData
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

- **Authoritative**: single, canonical event for “how successful was ADE and why?”
- **Standard structure**: consistent node shape across scopes, intentional naming.
- **Deterministic**: rollups and counts never contradict table-level truth.
- **Failure-tolerant**: summary emitted even on errors, containing partial progress.
- **Size-aware**: avoid raw cell values; cap candidates per column.

### 4.2 Summary schema (v{{SCHEMA_VERSION}})

`engine.run.completed` payload (in `data`) follows the contract in `pydantic_v2.md`:

- Root includes: `schema_version`, `scope="run"`, `execution`, `evaluation`, `counts`, `validation`, `fields`, `outputs`, `workbooks[]`.
- Workbook includes `locator`, `sheets[]` and similar rollups.
- Sheet includes `locator`, `tables[]`, plus optional scan stats.
- Table includes `locator`, `structure` (region/header/data/columns), `fields` rollup, `outputs` (output range).

Key naming decisions:

- `execution` = runtime success/failure (status, failure).
- `evaluation` = semantic success (outcome + findings).
- `outputs` = produced file/range pointers (NOT “artifacts”).
- `structure.columns` = ordered physical columns.
- Avoid ambiguous “columns” vs “headers”: table structure uses `columns`; header normalization lives under `column.header.normalized`.

### 4.3 Key flows / pipelines

**Flow A — Per-sheet scan**
- `_materialize_rows()` produces `rows` plus scan stats:
  - `rows_emitted`, `stopped_early`, `truncated_rows`.
- Builder records scan stats on the sheet node.

**Flow B — Per-table summary**
- For each detected table region:
  - builder captures region bounds (header/data row indices), header inferred flag
  - builder captures physical columns (index, raw/normalized header, non_empty_cells)
  - mapping diagnostics recorded per column:
    - status (mapped/ambiguous/unmapped/passthrough)
    - selected field + score
    - top-N candidates (field/score)
    - reason for unmapped (no_signal, non_positive, duplicate_field, etc.)
  - builder captures validation rollups and output range after render

**Flow C — Rollups + grading**
- Roll up deterministic sums across child nodes (tables → sheets → workbooks → run).
- Compute `evaluation.outcome` and `evaluation.findings` from rollups (see supporting-docs).

**Flow D — Emit `engine.run.completed` once**
- In `Engine.run()`, emit run summary event in a `finally` path so failures still produce summaries.
- Ensure log level does not suppress the summary event needed by `ade-api` (policy decision below).

### 4.4 Open questions / decisions

- **Log-level policy for summary:** If `--quiet` sets WARNING level, INFO events may be suppressed. Decision: {{DECIDE_LOG_POLICY}}.
- **Derived fields:** Count derived fields separately or ignore for v1? Decision: {{DECIDE_DERIVED_FIELDS_HANDLING}}.
- **Candidate list size:** Default N candidates per column: {{DECIDE_CANDIDATE_TOP_N}}.
- **Ambiguity definition:** When is a mapping “ambiguous” vs “unmapped”? Decision: {{DECIDE_AMBIGUITY_RULE}}.

---

## 5. Implementation & notes for agents

### 5.1 Implementation steps (suggested order)

1. Create `summary_schema.py` with strict Pydantic v2 models for v{{SCHEMA_VERSION}}.
2. Implement `summary_builder.py`:
   - incremental accumulation (per sheet scan, per table completion)
   - rollups and invariant enforcement
   - grading + findings generation
3. Instrument pipeline:
   - return scan stats from `_materialize_rows()`
   - store region fields on `TableData`
   - store mapping diagnostics (including candidates and unmapped reason)
   - store `output_range` on `TableData`
4. Update `ade_engine/logging.py`:
   - register new strict payload model for `engine.run.completed`
5. Update `Engine.run()`:
   - create builder early
   - pass builder through pipeline calls
   - emit run summary event exactly once, even on failure
6. Add tests:
   - schema validation for a representative run payload
   - rollup invariants
   - partial failure still emits a summary with partial progress

### 5.2 Testing notes

- Unit test the builder with synthetic table summaries (fast, deterministic).
- Integration test: run a minimal pipeline, assert that the emitted `engine.run.completed` payload validates against schema and includes expected counts/mapping.


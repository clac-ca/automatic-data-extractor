# Hooks & Extensibility

This document describes the **hook system** that lets `ade_config` plug custom
logic into well‑defined points of an ADE engine run, without changing the
engine core.

Hooks are how configs:

- add custom reporting,
- adjust tables or mappings,
- decorate the final workbook,
- emit metrics or integrate with external systems.

It assumes you’ve read the top‑level `README.md` and have a basic picture of
the pipeline (`extract → mapping → normalize → write`).

## Terminology

| Concept        | Term in code      | Notes                                                     |
| -------------- | ----------------- | --------------------------------------------------------- |
| Run            | `run`             | One call to `Engine.run()` or one CLI invocation          |
| Config package | `config_package`  | Installed `ade_config` package for this run               |
| Config version | `manifest.version`| Version declared by the config package manifest           |
| Build          | build             | Virtual environment built for a specific config version   |
| User data file | `source_file`     | Original spreadsheet on disk                              |
| User sheet     | `source_sheet`    | Worksheet/tab in the spreadsheet                          |
| Canonical col  | `field`           | Defined in manifest; never call this a “column”           |
| Physical col   | column            | B / C / index 0,1,2… in a sheet                           |
| Output workbook| normalized workbook| Written to `output_dir`; includes mapped + normalized data|

Hooks follow this vocabulary for consistency with runtime, artifact, and telemetry.

---

## 1. Mental model

At a high level:

- Each engine run has a single **`RunContext`** (passed into script APIs as `run`).
- The engine executes the pipeline in phases.
- At certain phases, it calls **hook functions** defined in `ade_config.hooks`.
- Hooks receive:
  - the current `RunContext`,
  - shared per‑run `run_state` dict,
  - the manifest,
  - artifact and telemetry sinks,
  - and phase‑specific objects (tables, workbook, result).

Hooks are **config‑owned**:

- The engine defines *when* hooks are called and *what* data they see.
- The config defines *what* those hooks do.

There is no global/shared state between runs; hooks only see per‑run state
through `RunContext` and `run_state` (exposed as `state` for backward
compatibility).

---

## 2. Hook stages (lifecycle)

The engine exposes five hook stages. They are configured in the manifest and
invoked in this order:

| Stage name        | When it runs                                       | What is available / allowed to change                                  |
| ----------------- | -------------------------------------------------- | ----------------------------------------------------------------------- |
| `on_run_start`    | After manifest + telemetry initialized, before IO | Read/initialize `run_state`, add notes, never touches tables or workbook|
| `on_after_extract`| After `RawTable[]` built, before column mapping   | Inspect/modify `RawTable` objects                                       |
| `on_after_mapping`| After `MappedTable[]` built, before normalization | Inspect/modify `MappedTable` objects (`column_map.mapped_columns` / `unmapped_columns`) |
| `on_before_save`  | After `NormalizedTable[]`, before writing files   | Inspect `NormalizedTable[]`, modify `Workbook` (formatting, summary)    |
| `on_run_end`      | After run success/failure determined              | Inspect `RunResult`, emit metrics/notes, **no further pipeline changes** |

Key points:

- Hooks in a stage run **sequentially, in manifest order**.
- `on_run_start` and `on_run_end` are for run‑level concerns only.
- `on_after_extract` / `on_after_mapping` / `on_before_save` may **mutate**
  objects they receive, as long as they keep them structurally valid.

---

## 3. Config & manifest wiring

Hooks are configured in the `hooks` section of `manifest.json`.

### 3.1 Manifest structure

Example:

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
````

Rules:

* Stage keys (`on_run_start`, `on_after_extract`, etc.) are **optional**:

  * Omitted stage → no hooks for that stage.
* Each entry is a module string **relative to the `ade_config` package root**, e.g. `"hooks.on_run_start"`.
* Hooks for a stage run in **the array order**.

### 3.2 Module resolution

For each entry:

* `"hooks.on_run_start"` → module: `ade_config.hooks.on_run_start`
* `"hooks.reporting.end_of_run"` → module:
  `ade_config.hooks.reporting.end_of_run`

If a hook module cannot be imported, the engine:

* raises a config‑load error (the run fails before pipeline work starts), and
* records a useful error message.

---

## 4. HookRegistry and invocation

Internally, the config loader builds a **`HookRegistry`** from the manifest.

Responsibilities:

* Resolve manifest hook module strings into importable module names.
* Import modules once per run.
* Discover the callable to execute (entrypoint).
* Group hooks by stage (`on_run_start`, `on_after_extract`, etc.) in order.

The pipeline orchestrator builds a `HookContext` for each stage and dispatches
it to hooks; if a stage has no configured hooks, `HookRegistry` is a no‑op. `HookStage` enum values are exactly:

```python
class HookStage(str, Enum):
    ON_RUN_START = "on_run_start"
    ON_AFTER_EXTRACT = "on_after_extract"
    ON_AFTER_MAPPING = "on_after_mapping"
    ON_BEFORE_SAVE = "on_before_save"
    ON_RUN_END = "on_run_end"
```

---

## 5. Hook function API

Hook modules are regular Python modules in `ade_config.hooks.*`.

### 5.1 Recommended signature (context-first)

Hooks should take a single `HookContext` argument for consistency:

```python
from dataclasses import dataclass
from typing import Any
from ade_engine.config.hook_registry import HookContext, HookStage  # legacy path: ade_engine.config_runtime.hook_registry
from ade_engine.core.types import RunResult, RunContext
from ade_engine.core.pipeline import RawTable, MappedTable, NormalizedTable
from ade_engine.infra.artifact import ArtifactSink
from ade_engine.infra.telemetry import EventSink, PipelineLogger
from openpyxl import Workbook

@dataclass
class HookContext:
    run: RunContext
    run_state: dict[str, Any]
    manifest: ManifestContext
    artifact: ArtifactSink
    events: EventSink | None
    tables: list[RawTable | MappedTable | NormalizedTable] | None
    workbook: Workbook | None
    result: RunResult | None
    logger: PipelineLogger
    stage: HookStage

def run(context: HookContext) -> None:
    context.logger.note("Run started", stage=context.stage.value)
```

Guidelines:

* Use `context.run_state` for mutable per‑run data; treat `context.run` as read‑only engine context.
* Use `context.logger` for notes/events; reach for `context.artifact`/`context.events` only when you need sink-level control.
* `context.tables`, `context.workbook`, and `context.result` are stage-dependent and may be `None`.
* If you choose to expose a keyword‑only hook signature instead of the context object, include `**_` to absorb new parameters.

---

## 6. What hooks are allowed to mutate

Hooks have real power; this section defines what is safe to mutate at each
stage.

### 6.1 `run_state` (aka `state` in scripts)

* `run_state` is the same dict exposed to detectors, transforms, validators, and
  hooks.
* It is **per run**; no sharing between runs.
* You can freely add, update, or delete keys.
* Typical usage:

  * caches,
  * cross‑table aggregates,
  * counters.

### 6.2 `tables`

* `on_after_extract`:

  * Receives `RawTable[]`.
  * You may:

    * reorder tables,
    * drop tables,
    * tweak header or data rows (e.g., trimming, fixing obvious anomalies).
  * Keep invariants intact:

    * `header_row` and `data_rows` must remain aligned with `header_row_index`,
      `first_data_row_index`, `last_data_row_index`.

* `on_after_mapping`:

  * Receives `MappedTable[]`.
  * You may:

    * override mappings for specific columns (`column_map.mapped_columns`),
    * adjust `column_map.unmapped_columns` (drop/rename extras),
    * change field order if your writer mode supports it.
  * Be careful not to introduce holes or duplicates in mapping.

* `on_before_save`:

  * Receives `NormalizedTable[]`.
  * You may:

    * reorder tables for writing,
    * drop tables,
    * (carefully) adjust `validation_issues` collections.
  * Individual row values are usually better handled during normalization,
    not here, but small fixes are allowed if necessary.

### 6.3 `workbook` (on_before_save only)

* `workbook` is an openpyxl `Workbook` that the engine will save after the
  hook stage.
* You may:

  * create new sheets (e.g., summary, readme, metrics),
  * adjust cell formatting, column widths, freeze panes, filters,
  * add formulas or static metadata cells.
* Do **not**:

  * rename or delete sheets created by the engine unless you know exactly how
    the writer behaves,
  * change the shape of existing data ranges in ways that break downstream
    expectations.

### 6.4 `result` (on_run_end only)

* `result` is a `RunResult` instance.
* It is treated as **immutable** by hooks:

  * Do not modify it.
  * Use it only for reporting (e.g., log/telemetry/metrics).

---

## 7. Common patterns (examples)

Below are typical uses of each hook stage.

### 7.1 `on_run_start`: initialize and annotate

```python
# ade_config/hooks/on_run_start.py
def run(ctx):
    ctx.run_state["start_timestamp"] = ctx.run.started_at.isoformat()
    ctx.run_state["config_version"] = ctx.manifest["info"]["version"]

    ctx.logger.note(
        "Run started",
        config_title=ctx.manifest["info"].get("title"),
        config_version=ctx.manifest["info"]["version"],
    )
```

### 7.2 `on_after_extract`: table sanity checks

```python
# ade_config/hooks/on_after_extract.py
def run(ctx):
    for t in ctx.tables or []:
        ctx.logger.note(
            "Extracted table",
            file=str(t.source_file),
            sheet=t.source_sheet,
            row_count=len(t.data_rows),
            header_row_index=t.header_row_index,
        )

        if len(t.data_rows) == 0:
            ctx.logger.note(
                "Empty table detected",
                level="warning",
                file=str(t.source_file),
                sheet=t.source_sheet,
            )
```

### 7.3 `on_after_mapping`: tweak ambiguous mappings

```python
# ade_config/hooks/on_after_mapping.py
def run(ctx):
    for table in ctx.tables or []:
        # Example: ensure at most one "email" mapping
        seen_email = False
        for m in table.mapping:
            if m.field == "email":
                if seen_email:
                    ctx.logger.note(
                        "Dropping duplicate email mapping",
                        level="warning",
                        header=m.header,
                        column_index=m.source_column_index,
                    )
                    m.field = "raw_email_candidate"
                else:
                    seen_email = True
```

### 7.4 `on_before_save`: add summary sheet

```python
# ade_config/hooks/on_before_save.py
def run(ctx):
    summary = ctx.workbook.create_sheet(title="ADE Summary")

    summary["A1"] = "Config"
    summary["B1"] = ctx.manifest["info"]["title"]
    summary["A2"] = "Version"
    summary["B2"] = ctx.manifest["info"]["version"]

    row = 4
    summary[f"A{row}"] = "Table"
    summary[f"B{row}"] = "Rows"
    row += 1

    for t in ctx.tables or []:
        summary[f"A{row}"] = f"{t.mapped.raw.source_file.name}:{t.output_sheet_name}"
        summary[f"B{row}"] = len(t.rows)
        row += 1

    ctx.logger.note("Added ADE Summary sheet")
```

### 7.5 `on_run_end`: aggregate metrics

```python
# ade_config/hooks/on_run_end.py
def run(ctx):
    duration_ms = (ctx.run.completed_at - ctx.run.started_at).total_seconds() * 1000
    status = ctx.result.status

    ctx.logger.event(
        "run_summary",
        level="info",
        status=status,
        duration_ms=duration_ms,
        processed_files=list(ctx.result.processed_files),
    )

    ctx.artifact.note(
        f"Run {status} in {duration_ms:.0f}ms",
        level="info",
    )
```

---

## 8. Error handling & safety

### 8.1 Effect of exceptions

* Any uncaught exception in a hook:

  * marks the run as **failed**,
  * records a `HookExecutionError` (or equivalent) in artifact/telemetry,
  * stops further pipeline work.

The engine **does not** swallow hook errors silently.

### 8.2 Best practices

* Validate your assumptions early and fail fast with clear messages if they
  are violated.
* If you depend on external systems (HTTP, DB, etc.):

  * handle timeouts and transient failures,
  * decide when to treat them as fatal vs. degraded behavior.
* Prefer `logger.note` / `logger.event` over raw `print` or ad‑hoc logging.

---

## 9. Versioning

Breaking changes to script APIs are coordinated via:

* `script_api_version` in the manifest, and
* documentation that describes the new expectations.

When in doubt, check:

* `ade_engine.schemas.manifest.ManifestV1` for the manifest version you
  target, and
* `hooks.py` for any new `HookStage` or context fields.

---

## 10. Hook author checklist

When adding or modifying hooks in a config:

1. **Decide the stage(s)** you need:

   * *Run metadata?* → `on_run_start` / `on_run_end`
   * *Inspect/reshape tables?* → `on_after_extract` / `on_after_mapping`
   * *Workbook styling/reporting?* → `on_before_save`
2. **Add entries to `manifest.json`** under `hooks` with correct module strings.
3. **Create hook modules** in `ade_config/hooks/` with a `run(...)` function:

   * use keyword‑only signature,
4. **Use `logger` for notes/events**, `run_state` for shared run data.
5. **Mutate only what’s safe** for the stage (see section 6).
6. **Test end‑to‑end**:

   * run the engine locally on sample files,
   * inspect `artifact.json` and `events.ndjson`,
   * verify hooks behave as expected.

With this model, hooks give you powerful extension points while keeping the
core engine small, predictable, and reusable across many configs.

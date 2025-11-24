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

---

## 1. Mental model

At a high level:

- Each engine run has a single **`RunContext`** (`job` in script APIs).
- The engine executes the pipeline in phases.
- At certain phases, it calls **hook functions** defined in `ade_config.hooks`.
- Hooks receive:
  - the current `RunContext`,
  - shared per‑run `state` dict,
  - the manifest and `env`,
  - artifact and telemetry sinks,
  - and phase‑specific objects (tables, workbook, result).

Hooks are **config‑owned**:

- The engine defines *when* hooks are called and *what* data they see.
- The config defines *what* those hooks do.

There is no global/shared state between runs; hooks only see per‑run state
through `RunContext` and `state`.

---

## 2. Hook stages (lifecycle)

The engine exposes five hook stages. They are configured in the manifest and
invoked in this order:

| Stage name        | When it runs                                       | What is available / allowed to change                                  |
| ----------------- | -------------------------------------------------- | ----------------------------------------------------------------------- |
| `on_run_start`    | After manifest + telemetry initialized, before IO | Read/initialize `state`, add notes, never touches tables or workbook    |
| `on_after_extract`| After `RawTable[]` built, before column mapping   | Inspect/modify `RawTable` objects                                       |
| `on_after_mapping`| After `MappedTable[]` built, before normalization | Inspect/modify `MappedTable` objects (mappings and extras)              |
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
    "on_run_start": [
      { "script": "hooks/on_run_start.py", "enabled": true }
    ],
    "on_after_extract": [
      { "script": "hooks/on_after_extract.py" }
    ],
    "on_after_mapping": [
      { "script": "hooks/on_after_mapping.py" }
    ],
    "on_before_save": [
      { "script": "hooks/on_before_save.py" }
    ],
    "on_run_end": [
      { "script": "hooks/on_run_end.py" }
    ]
  }
}
````

Rules:

* Stage keys (`on_run_start`, `on_after_extract`, etc.) are **optional**:

  * Omitted stage → no hooks for that stage.
* Each entry:

  ```jsonc
  { "script": "hooks/on_run_start.py", "enabled": true }
  ```

  * `script` is a path **relative to the `ade_config` package root**.
  * `enabled` is optional; default is `true`.
* Hooks for a stage run in **the array order**.

### 3.2 Script path → module

For each entry:

* `script: "hooks/on_run_start.py"` → module: `ade_config.hooks.on_run_start`
* `script: "hooks/reporting/end_of_run.py"` → module:
  `ade_config.hooks.reporting.end_of_run`

If a hook module cannot be imported, the engine:

* raises a config‑load error (the run fails before pipeline work starts), and
* records a useful error message.

---

## 4. HookRegistry and invocation

Internally, `config_runtime` builds a **`HookRegistry`** from the manifest.

Responsibilities:

* Resolve `script` paths into importable module names.
* Import modules once per run.
* Discover the callable to execute (entrypoint).
* Group hooks by stage (`on_run_start`, `on_after_extract`, etc.) in order.

The pipeline orchestrator then does something conceptually like:

```python
# on_run_start
hooks.call(
    stage="on_run_start",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    logger=pipeline_logger,
)

# on_after_extract
hooks.call(
    stage="on_after_extract",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    tables=raw_tables,
    logger=pipeline_logger,
)

# on_after_mapping
hooks.call(
    stage="on_after_mapping",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    tables=mapped_tables,
    logger=pipeline_logger,
)

# on_before_save
hooks.call(
    stage="on_before_save",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    tables=normalized_tables,
    workbook=workbook,
    logger=pipeline_logger,
)

# on_run_end
hooks.call(
    stage="on_run_end",
    job=ctx,
    state=ctx.state,
    manifest=ctx.manifest.raw,
    env=ctx.env,
    artifact=artifact_sink,
    events=event_sink,
    result=run_result,
    logger=pipeline_logger,
)
```

If a stage has no configured hooks, `HookRegistry` is a no‑op for that stage.

---

## 5. Hook function API

Hook modules are regular Python modules in `ade_config.hooks.*`.

### 5.1 Recommended signature

The engine looks for a **`run` function** with a keyword‑only signature:

```python
def run(
    *,
    job,               # RunContext (called "job" for historical reasons)
    state: dict,
    manifest: dict,
    env: dict | None,
    artifact,          # ArtifactSink
    events,            # EventSink | None
    tables=None,       # stage-dependent: RawTable[] / MappedTable[] / NormalizedTable[]
    workbook=None,     # openpyxl.Workbook for on_before_save
    result=None,       # RunResult for on_run_end
    logger=None,       # PipelineLogger
    **_,
) -> None:
    ...
```

Guidelines:

* Always accept `**_` to remain forward compatible with future parameters.
* Treat `job` as read‑only engine context; use `state` for mutable per‑run data.
* Use `logger` as the primary way to emit notes/events:

  * `logger.note("...", level="info", **details)`
  * `logger.event("...", level="info", **payload)`
* Use `artifact` and `events` only if you need direct sink control.

### 5.2 Optional `HookContext` style

The engine **may** also support a single‑argument style if you prefer:

```python
def run(ctx) -> None:
    # ctx.job, ctx.state, ctx.manifest, ctx.env, ctx.artifact, ctx.events,
    # ctx.tables, ctx.workbook, ctx.result, ctx.logger
    ...
```

This is purely a convenience; the recommended, explicit style is the
keyword‑only function.

---

## 6. What hooks are allowed to mutate

Hooks have real power; this section defines what is safe to mutate at each
stage.

### 6.1 `state`

* `state` is the same dict exposed to detectors, transforms, validators, and
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

    * `header_row` and `data_rows` must remain aligned with `header_index`,
      `first_data_index`, `last_data_index`.

* `on_after_mapping`:

  * Receives `MappedTable[]`.
  * You may:

    * override mappings for specific columns,
    * adjust `extras` (`ExtraColumn` list),
    * change field order if your writer mode supports it.
  * Be careful not to introduce holes or duplicates in mapping.

* `on_before_save`:

  * Receives `NormalizedTable[]`.
  * You may:

    * reorder tables for writing,
    * drop tables,
    * (carefully) adjust `issues` collections.
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
def run(*, job, state, manifest, env, artifact, events, logger=None, **_):
    state["start_timestamp"] = job.started_at.isoformat()
    state["config_version"] = manifest["info"]["version"]

    logger.note(
        "Run started",
        config_title=manifest["info"].get("title"),
        config_version=manifest["info"]["version"],
    )
```

### 7.2 `on_after_extract`: table sanity checks

```python
# ade_config/hooks/on_after_extract.py
def run(*, tables, logger, **_):
    for t in tables:
        logger.note(
            "Extracted table",
            file=str(t.source_file),
            sheet=t.source_sheet,
            row_count=len(t.data_rows),
            header_row_index=t.header_index,
        )

        if len(t.data_rows) == 0:
            logger.note(
                "Empty table detected",
                level="warning",
                file=str(t.source_file),
                sheet=t.source_sheet,
            )
```

### 7.3 `on_after_mapping`: tweak ambiguous mappings

```python
# ade_config/hooks/on_after_mapping.py
def run(*, tables, logger, **_):
    for table in tables:
        # Example: ensure at most one "email" mapping
        seen_email = False
        for m in table.mapping:
            if m.field == "email":
                if seen_email:
                    logger.note(
                        "Dropping duplicate email mapping",
                        level="warning",
                        header=m.header,
                        column_index=m.index,
                    )
                    m.field = "raw_email_candidate"
                else:
                    seen_email = True
```

### 7.4 `on_before_save`: add summary sheet

```python
# ade_config/hooks/on_before_save.py
def run(*, tables, workbook, manifest, logger=None, **_):
    summary = workbook.create_sheet(title="ADE Summary")

    summary["A1"] = "Config"
    summary["B1"] = manifest["info"]["title"]
    summary["A2"] = "Version"
    summary["B2"] = manifest["info"]["version"]

    row = 4
    summary[f"A{row}"] = "Table"
    summary[f"B{row}"] = "Rows"
    row += 1

    for t in tables:
        summary[f"A{row}"] = f"{t.mapped.raw.source_file.name}:{t.output_sheet_name}"
        summary[f"B{row}"] = len(t.rows)
        row += 1

    if logger:
        logger.note("Added ADE Summary sheet")
```

### 7.5 `on_run_end`: aggregate metrics

```python
# ade_config/hooks/on_run_end.py
def run(*, job, state, result, artifact, logger=None, **_):
    duration_ms = (job.completed_at - job.started_at).total_seconds() * 1000
    status = result.status

    if logger:
        logger.event(
            "run_summary",
            level="info",
            status=status,
            duration_ms=duration_ms,
            processed_files=list(result.processed_files),
        )

    artifact.note(
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

## 9. Compatibility & versioning

To keep configs working across versions:

* Hook functions should:

  * use keyword‑only parameters, and
  * always include `**_` to ignore new parameters.
* The engine may add new keyword arguments over time (e.g., additional
  metadata).

Breaking changes to script APIs are coordinated via:

* `config_script_api_version` in the manifest, and
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
2. **Add entries to `manifest.json`** under `hooks` with correct `script` paths.
3. **Create hook modules** in `ade_config/hooks/` with a `run(...)` function:

   * use keyword‑only signature,
   * include `**_` for forward compatibility.
4. **Use `logger` for notes/events**, `state` for shared run data.
5. **Mutate only what’s safe** for the stage (see section 6).
6. **Test end‑to‑end**:

   * run the engine locally on sample files,
   * inspect `artifact.json` and `events.ndjson`,
   * verify hooks behave as expected.

With this model, hooks give you powerful extension points while keeping the
core engine small, predictable, and reusable across many configs.
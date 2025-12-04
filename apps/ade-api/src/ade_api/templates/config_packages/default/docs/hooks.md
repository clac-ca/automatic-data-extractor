# Hooks

Hooks are **optional lifecycle callbacks** that let you inject custom behavior at specific points in the pipeline.

Enable them in `manifest.json` under the `"hooks"` section and implement a `run(...)` function in `ade_config/hooks/*.py`.

Hooks never replace pipeline stages—
they let you *observe*, *log*, *decorate*, or *lightly modify* work in progress.

---

## Lifecycle Stages

Hooks are executed in this order:

1. **`on_run_start`**
   Runs once before anything else—manifest and telemetry are initialized, but no I/O has occurred.

2. **`on_after_extract`**
   Runs after `ExtractedTable` objects are produced.

3. **`on_after_mapping`**
   Runs after field mapping is complete (you receive `MappedTable` objects).

4. **`on_before_save`**
   Runs after normalization and workbook creation, just before saving to disk.

5. **`on_run_end`**
   Runs once after everything has finished (success *or* failure).

Each hook receives only the arguments relevant for that stage.

---

## Hook Function Signature

Every hook implements a keyword-only `run(...)` entrypoint:

```py
def run(
    *,
    run=None,
    state: dict | None = None,
    manifest=None,
    tables=None,
    workbook=None,
    result=None,
    stage=None,
    logger=None,
    event_emitter=None,
    **_,    # required for forward compatibility
):
    ...
```

### Argument Overview

| Parameter         | Description                                                |
| ----------------- | ---------------------------------------------------------- |
| **run**           | The run context (`run_id`, `metadata`, etc.).              |
| **state**         | A shared dict persisted across all hooks for this run.     |
| **manifest**      | Manifest context used for this execution.                  |
| **tables**        | Stage-dependent: `ExtractedTable[]` or `MappedTable[]`.    |
| **workbook**      | `openpyxl.Workbook` given only to `on_before_save`.        |
| **result**        | Contains status + output paths; available in `on_run_end`. |
| **logger**        | A standard Python logger for human-friendly logs.          |
| **event_emitter** | Emit structured events (`custom(...)`) if needed.          |
| ******_           | Placeholder for future fields (always include).            |

Hooks should **never assume any argument will be present**—each stage passes only what’s relevant.

---

## Return Values by Stage

| Stage                | Allowed Return       | Meaning                                                                                    |
| -------------------- | -------------------- | ------------------------------------------------------------------------------------------ |
| **on_after_extract** | `list` or `None`     | Return a new list of `ExtractedTable` objects, or return `None` to keep the original list. |
| **on_after_mapping** | `list` or `None`     | Same pattern, but with `MappedTable` objects.                                              |
| **on_before_save**   | `Workbook` or `None` | Return a replacement workbook, or `None` to keep the original.                             |
| **on_run_start**     | `None`               | No return value is used.                                                                   |
| **on_run_end**       | `None`               | No return value is used.                                                                   |

Returning `None` always means: **“leave the pipeline output unchanged.”**

---

## Common Hook Use Cases

### ✔ Logging lifecycle checkpoints

Use `logger.info(...)` to record when stages begin/finish:

* Run started
* Extracted 4 tables
* Mapped 32 fields
* Applying workbook styling
* Run completed with status=success

### ✔ Emitting structured telemetry

Rare, high-value events (not scoring data—engine handles that automatically):

```py
event_emitter.custom("hook.my_custom_event", ...)
```

Useful for monitoring dashboards, debugging, audit trails, or integration with external systems.

### ✔ Reshaping the table list

During:

* `on_after_extract`
* `on_after_mapping`

You can:

* Drop empty tables
* Reorder tables
* Merge/split tables
* Add metadata or flags
* Filter out known irrelevant sheets

### ✔ Decorating the Excel workbook

During `on_before_save` you can:

* Freeze panes
* Add Excel tables or styles
* Append summary sheets
* Insert metadata or run statistics
* Apply conditional formatting

### ✔ Final run reporting

During `on_run_end` you can:

* Send a Slack/email notification
* Write audit logs
* Emit end-of-run metrics
* Clean up temporary state

---

## Best Practices

* Use hooks **sparingly** for customization points, not core logic.
* Keep processing light—heavy logic belongs in detectors or transforms.
* Avoid modifying tables in place unless intentional.
* Always include `**_` so your hooks remain forward compatible.
* Remember: the engine already emits detailed telemetry for scoring, progress, and debug data—your hooks should focus on *your* custom behavior.
> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Backwards compatibility is **NOT required** for this workpackage.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Define the new hook context API (names + fields) and update `HookName` docs/templates.
* [x] Implement new hook context dataclasses in `ade_engine/models/extension_contexts.py`.
* [x] Update `Registry.run_hooks()` to build the new contexts.
* [x] Pass `TableResult` into `on_table_written` hooks.
* [x] Pass `list[TableResult]` into `on_sheet_end` hooks.
* [x] Update config package templates in `ade_engine/extensions/templates/config_packages/default/...`.
* [x] Add/adjust engine tests for hook context payloads (or add minimal coverage if none exist).
* [ ] Manual validation: run `ade-engine process file --debug` and confirm a hook can write an “original headers” diagnostic row without using `state`.

---

# ADE engine: make hook contexts intuitive (source/output) + expose `TableResult`

## 1. Objective

**Goal:**
Make ADE engine hooks easier and more intuitive by:

1) Making hook parameters unambiguous about **source (input)** vs **output** objects.
2) Exposing the engine’s computed table facts (`TableResult`) to output-stage hooks so config authors can build diagnostics (like “original header row”) without:
   - re-reading the input worksheet in hooks, or
   - shuttling data through `state`.

**Backwards compatibility:**
Not required. It’s OK to rename hook args and update templates accordingly.

---

## 2. Context (What you are starting from)

Current behavior (ade-engine ~1.7.x):

* `on_table_mapped` hooks receive the **source** sheet/workbook/region.
* `on_table_written` hooks receive the **output** sheet/workbook/region.
* Both stages use the same parameter names (`sheet`, `workbook`, `table_region`), which is confusing because the meaning changes by stage.
* Output hooks do not receive mapping facts (original headers, mapped columns, etc.). Those facts exist internally as `TableResult` but are not passed into hooks.

Real-world consequence:

* To insert a diagnostic row showing “original input headers” under the output header, config code currently has to:
  - capture original headers early (e.g., in `on_table_mapped`) and store them in `state`, then
  - insert rows later (e.g., in `on_sheet_end`) and update Excel table refs manually.

This workpackage makes that diagnostic use case straightforward and engine-native.

---

## 3. Target architecture / structure (ideal)

### 3.1 Naming convention (public hook args)

Use explicit `source_*` and `output_*` names to avoid stage-dependent meaning:

* `source_workbook`, `source_sheet`, `source_region`
* `output_workbook`, `output_sheet`, `output_region`
* `write_table` for the Polars table actually written to output (post output policies)

### 3.2 Key ergonomic additions

* `table_result: TableResult` passed into `on_table_written` hooks.
* `tables: Sequence[TableResult]` passed into `on_sheet_end` hooks, ordered as written (top-to-bottom).

With those two, a config hook can do:

* `original_by_field = {m.field_name: m.header for m in table_result.mapped_columns}`
* Insert a row under the output header and populate original headers for mapped fields.

---

## 4. Proposed public hook signatures (new API)

These are example signatures (templates should match).

### 4.1 Workbook hooks

```py
def on_workbook_start(
    *,
    source_workbook: openpyxl.Workbook,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: dict[str, Any],
    input_file_name: str,
    logger: RunLogger,
) -> None: ...

def on_workbook_before_save(
    *,
    output_workbook: openpyxl.Workbook,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: dict[str, Any],
    input_file_name: str,
    logger: RunLogger,
) -> None: ...
```

### 4.2 Sheet hooks

```py
def on_sheet_start(
    *,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,
    source_workbook: openpyxl.Workbook,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: dict[str, Any],
    input_file_name: str,
    logger: RunLogger,
) -> None: ...

def on_sheet_end(
    *,
    output_sheet: openpyxl.worksheet.worksheet.Worksheet,
    output_workbook: openpyxl.Workbook,
    tables: Sequence[TableResult],  # <-- new
    settings: Settings,
    metadata: Mapping[str, Any],
    state: dict[str, Any],
    input_file_name: str,
    logger: RunLogger,
) -> None: ...
```

### 4.3 Table hooks

```py
def on_table_mapped(
    *,
    table: pl.DataFrame,
    source_sheet: openpyxl.worksheet.worksheet.Worksheet,
    source_workbook: openpyxl.Workbook,
    source_region: TableRegion,
    table_index: int,
    settings: Settings,
    metadata: Mapping[str, Any],
    state: dict[str, Any],
    input_file_name: str,
    logger: RunLogger,
) -> pl.DataFrame | None: ...

def on_table_written(
    *,
    write_table: pl.DataFrame,
    output_sheet: openpyxl.worksheet.worksheet.Worksheet,
    output_workbook: openpyxl.Workbook,
    output_region: TableRegion,
    table_index: int,
    table_result: TableResult,  # <-- new
    settings: Settings,
    metadata: Mapping[str, Any],
    state: dict[str, Any],
    input_file_name: str,
    logger: RunLogger,
) -> None: ...
```

Notes:
* `table_result.source_region` + `table_result.mapped_columns[*].header` are the key pieces for “original headers” diagnostics.
* For sheet-level diagnostics that need to safely insert rows, `on_sheet_end(output_sheet, tables=...)` is the right stage.

---

## 5. Implementation plan (ade-engine repo)

### 5.1 Files to change (expected)

```text
ade_engine/models/extension_contexts.py          # new/renamed hook context dataclasses
ade_engine/extensions/registry.py                # build new contexts; accept/pass new fields
ade_engine/application/pipeline/pipeline.py      # pass `table_result` to ON_TABLE_WRITTEN
ade_engine/application/engine.py                 # capture table_results per sheet; pass to ON_SHEET_END
ade_engine/extensions/templates/config_packages/default/src/ade_config/hooks/*.py
```

### 5.2 Concrete steps

1) **Define the new contexts**
   - Create new dataclasses for hook contexts (do not reuse a single `TableHookContext` for all stages).
   - Update `HookContext` union accordingly.

2) **Update registry hook dispatch**
   - Update `Registry.run_hooks()` to:
     - accept/require the new keyword args (e.g., `source_sheet`, `output_sheet`, `table_result`, `tables`),
     - construct the correct context type per hook stage, and
     - continue to call hooks via `call_extension(...)`.

3) **Pass TableResult into `on_table_written`**
   - In the pipeline right before calling `HookName.ON_TABLE_WRITTEN`, pass `table_result=table_result`.

4) **Pass all TableResults into `on_sheet_end`**
   - In `Engine.run()`, store `table_results = pipeline.process_sheet(...)`.
   - Pass `tables=table_results` into `HookName.ON_SHEET_END`.

5) **Update templates**
   - Update the default config templates to the new hook arg names.
   - Add an example hook in the templates:
     - `on_sheet_end_example_insert_original_headers_row(...)` that uses `tables[*].mapped_columns` to write a diagnostic row.

6) **Tests / validation**
   - Add a small test (or minimal coverage) that asserts:
     - `on_table_written` receives `table_result` populated, and
     - `on_sheet_end` receives the list of `TableResult` objects in order.
   - Manual: run `ade-engine process file --debug` with a config hook that writes original headers without using `state`.

---

## 6. Acceptance criteria

* A config author can implement “insert original input headers under the output header row” using only:
  - `on_sheet_end(output_sheet, tables=[...])`, and
  - `TableResult.mapped_columns[*].header` (no `state` workaround, no reading the input workbook).
* Hook argument names clearly indicate source vs output objects.
* Default template hooks compile and reflect the new API.

---

## 7. Example: diagnostic row hook (should become a template example)

```py
def on_sheet_end_insert_original_headers_row(
    *,
    output_sheet,
    output_workbook,
    tables,
    **_,
) -> None:
    from openpyxl.utils.cell import range_boundaries

    # Insert bottom-up so earlier inserts don't shift the row coordinates
    # for tables that appear later on the sheet.
    for tr in reversed(list(tables)):
        if tr.output_region is None:
            continue

        original_by_field = {m.field_name: m.header for m in tr.mapped_columns}

        header_row = tr.output_region.min_row
        insert_row = header_row + 1
        output_sheet.insert_rows(insert_row, amount=1)

        # Fill original header values for mapped canonical fields
        for col in range(tr.output_region.min_col, tr.output_region.max_col + 1):
            field_name = output_sheet.cell(row=header_row, column=col).value
            output_sheet.cell(row=insert_row, column=col).value = original_by_field.get(field_name)
```

Notes:
* This example intentionally ignores unmapped/passthrough output columns; mapped fields are the main debugging need.
* If the template also adds structured tables, you’ll still need to update each Excel table `ref` after row insertion.

> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this refactor.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as you complete tasks, and add new items when you discover more work.
> * Update placeholders (`{{LIKE_THIS}}`) with concrete details as you learn them.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

### Architecture & core API

* [x] Replace the current pipeline with the new **Workbook → Sheets → Tables** architecture (sheet-order + table-order preserved).
* [x] Introduce new domain terminology + types: `TableOrigin`, `TableRegion`, `ColumnMapping`, `ColumnMappingPatch`, `TablePlacement`, contexts.
* [x] Implement the new hook interface and contexts: `on_workbook_start`, `on_sheet_start`, `on_table_detected`, `on_table_mapped` (returns patch), `on_table_written`, `on_workbook_before_save`.
* [x] Implement table detection as a pluggable `TableDetector`.
* [x] Implement Extract → Map (+patch) → Normalize stages using **pure data** (no openpyxl cell mutations).
* [x] Implement Render/Write stage that writes normalized output into an **openpyxl output workbook** and returns a `TablePlacement` (`Worksheet + CellRange`).
* [x] Add configurable stacked-header merging (settings + detection + pipeline merge + reporting).

### Efficiency & safety conventions

* [x] Output workbook/worksheets are created at run start, but **cells are only created during render**.
* [x] Add `TableView` helper so hooks naturally stay within the written range.
* [x] Define and document the “no structural sheet edits in hooks” contract (no row/col insert/delete outside of renderer; style/comments are fine).

### Config packages (compatibility)

* [x] Keep the config package layout + manifest schema intact (pyproject + `src/ade_config/manifest.json` with `script_api_version: 3`, `columns.order/fields`, writer toggles, row/column detectors).
* [x] Change only the hook lifecycle: new workbook/sheet/table stages wired via manifest `hooks` entries and updated template modules (basic + advanced + LLM-assisted mapping examples).

### Refactor & deletions

* [x] Delete old types (`ExtractedTable`/`MappedTable` wrappers), old hook points, old engine runner, and related docs (no compat layer).
* [x] Update CLI/entrypoints to the new API and remove obsolete flags.

### Tests & docs

* [x] Rewrite unit tests for detector, mapping, patch validation, normalization, rendering placement, and hook calls.
* [x] Add integration tests that run end-to-end and assert output workbook content + styles/comments.
* [x] Rewrite documentation: architecture overview, terminology glossary, hook guide, examples, manifest spec. (New summaries added under src/ade_engine/docs/; legacy chapters archived as legacy stubs.)

---

### Current plan (Codex session)

- Reconcile this workpackage with the codebase and update the checklist as pieces land.
- Implement the new types/contexts + hook protocol and wire manifest/hook loading to the new lifecycle.
- Build the workbook → sheet → table pipeline (detector/extract/map/normalize/render) and adjust CLI entrypoints to call it.
- Refresh config package templates/hooks to the new lifecycle; add/adjust tests and docs for the new architecture.

# ADE Engine: Openpyxl-native Output Architecture

## 1. Objective

**Goal:**
Refactor ade-engine into a clean, predictable, and efficient pipeline that:

1. Walks every worksheet in an input workbook, in order.
2. Detects all tables on each worksheet by header rows (each header block = a table region).
3. Fully processes each region through **Extract → Map → Normalize**.
4. Writes results into a **new output workbook** using **real openpyxl objects**, preserving:

   * original sheet grouping
   * original sheet order
   * original table order *within* each sheet
5. Exposes hook points throughout the pipeline to support:

   * LLM-assisted mapping updates (mapping patch)
   * post-write styling/comments/number formats using real openpyxl objects
   * worksheet-level configuration
   * workbook-level finishing steps

**Non-goals (explicit):**

* No backwards compatibility.
* No attempt to preserve source formatting/comments by default (future opt-in).
* No streaming/write-only mode required now (can be an optional future extension).

---

## 2. Context (What you are starting from)

Current engine conceptually does:

* extract tables from source spreadsheets
* map extracted columns to canonical fields
* normalize rows
* write output workbook with openpyxl at the end

Current pain points:

* data objects don’t “feel” like openpyxl until the last step
* mapping stage is mostly metadata (nested `.extracted.` access)
* hooks aren’t naturally positioned for LLM mapping refinement
* future needs: add comments/styles/types naturally, using openpyxl APIs

## 2.5 Config packages (what stays the same)

Config packages stay as installable Script API v3 projects (see templates at `apps/ade-engine/templates/config_packages/default` and the mirrored API templates under `apps/ade-api/src/ade_api/templates/config_packages/default`). Layout:

```text
ade_config/
  manifest.json             # schema ade.manifest/v1, script_api_version: 3
  row_detectors/            # header/data voters
  column_detectors/         # per-canonical-field detectors (plus transforms/validators)
  hooks/                    # lifecycle modules (run(**kwargs))
```

`manifest.json` keeps `script_api_version: 3`, `columns.order/fields` (module paths relative to `ade_config`), and writer toggles (`append_unmapped_columns`, `unmapped_prefix`). Row/column detectors keep the existing keyword-only Script API v3 signatures and behavior; the refactor must wrap them in the new detector/mapper layers instead of changing their contract. The only config-package shift for this refactor is the hook lifecycle described in §4.5—hook modules stay under `ade_config/hooks/` with `run(**kwargs)` entrypoints, but the stage names/contexts change to the new workbook/sheet/table events.

Why configs exist (plain-language): the engine is generic plumbing that knows how to scan spreadsheets, map columns, normalize rows, and write an output workbook. The business-specific rules—what fields matter, how to detect them, how to clean them, and how to style/report results—live in **versioned config packages** so each customer/workspace can evolve independently. Shipping them as small Python packages keeps business logic isolated, testable, and upgradeable without changing the engine; you can pin a config version for a run, roll out a new version when rules change, and keep multiple configs side-by-side in the same deployment.

Detector scoring (plain-language): each column detector is scoped to its canonical field but can emit two shapes: a float (e.g., `0.8`) that applies only to its own field, or a dict (e.g., `{"first_name": 1.0, "last_name": -0.5}`) that nudges multiple fields up or down. The engine aggregates scores per field per column, picks the highest-scoring field above the manifest’s mapping threshold, and assigns that column; if nothing clears the bar and `append_unmapped_columns` is true, the column is kept as a prefixed passthrough. Cross-field dict returns are how a detector can say “this looks like X and definitely not Y” in one shot, without any changes to the Script API v3 contract.

---

## 3. Target architecture / structure (ideal)

### 3.1 Core idea

**Output openpyxl objects exist from the beginning** (workbook + worksheets), but are populated only during the **render/write** step for each normalized table. Hooks can mutate openpyxl objects safely when a table has been written and its output range is known.

### 3.2 Proposed file tree (new structure)

```text
apps/ade-engine/
  src/ade_engine/
    __init__.py
    engine.py                 # ADEngine orchestration (high-level run)
    types/
      origin.py               # TableOrigin, TableRegion, TablePlacement
      tables.py               # ExtractedTable, MappedTable, NormalizedTable
      mapping.py              # ColumnMapping, ColumnMappingPatch + validation
      issues.py               # ValidationIssue, Severity, codes
      contexts.py             # RunContext, WorksheetContext, TableContext, TableView
    hooks/
      base.py                 # no-op hooks base class
      protocol.py             # ADEHooks Protocol
      dispatcher.py           # optional multi-hook fanout
    detect/
      detector.py             # TableDetector Protocol + default implementation
      rules.py                # header detection rules (configurable)
    extract/
      extractor.py            # TableExtractor
    map/
      mapper.py               # ColumnMapper
      patch.py                # apply_patch() and validation
    normalize/
      normalizer.py           # TableNormalizer
    render/
      renderer.py             # TableRenderer (writes to openpyxl)
      layout.py               # SheetLayout (cursor + spacing policy)
    io/
      read.py                 # openpyxl load helpers
      write.py                # save helpers (thin)
    docs/
      architecture.md         # generated/maintained docs
      hooks.md
      manifest.md
  tests/
    unit/
      test_detector.py
      test_mapping_patch.py
      test_normalizer.py
      test_renderer_placement.py
      test_hooks_call_order.py
    integration/
      test_end_to_end_basic.py
      test_end_to_end_styles_comments.py
```

> **Agent instruction:** Adjust paths if repo structure differs—update this workpackage first.

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Simple mental model:** workbook → sheets → tables → write
* **Openpyxl-native output:** hooks can use stock openpyxl APIs (Worksheet/CellRange/Cell)
* **Efficient:** do not create output cells until render; avoid copying rows unnecessarily
* **Safe & predictable:** hooks get stable, scoped objects; table order preserved deterministically
* **Extensible:** LLM mapping updates via a dedicated mapping patch hook; future formatting/comments supported post-write

---

## 4.2 Terminology (single-source glossary)

* **Source workbook / worksheet:** input loaded via openpyxl (read-only recommended by default)
* **Output workbook / worksheet:** created at run start; written during render
* **TableRegion:** the detected rectangular block in a worksheet (bounds in Excel coordinates)
* **TableOrigin:** identity + stable ordering info (sheet_index/table_index)
* **ExtractedTable:** the raw header + raw rows extracted from a region (values only)
* **ColumnMapping:** mapping result describing canonical fields and passthrough/unmapped columns
* **ColumnMappingPatch:** a user/hook-provided change-set applied to the mapping (for LLM or manual overrides)
* **MappedTable:** a logical “mapped view” of extracted rows in canonical column order
* **NormalizedTable:** canonical header + normalized rows + validation issues (ready to write)
* **TablePlacement:** where a normalized table was written in the output worksheet (`Worksheet + CellRange`)
* **TableView:** convenience wrapper around a placement range for easy/safe styling/comments

---

## 4.3 Key components / modules

### ADEngine (orchestrator)

**Responsibility:** The high-level run loop that coordinates:

* openpyxl workbook setup
* sheet iteration
* detection/extract/map/normalize/write for each table
* hook invocation and mapping patch application
* final save

### TableDetector (detection)

**Responsibility:** For a given `source_worksheet`, return ordered `TableRegion` list.

### TableExtractor (extract)

**Responsibility:** Convert a `TableRegion` into an `ExtractedTable`:

* header = list[str]
* rows = list[list[Any]]
* include preview rows for the LLM mapping hook

### ColumnMapper (map)

**Responsibility:** Produce a `ColumnMapping` and a `MappedTable` view:

* canonical fields ordered by manifest
* passthrough/unmapped columns optionally included
* `MappedTable.rows` is ideally a projection view (no full copy)

### Mapping Patch (LLM hook)

**Responsibility:** Hook returns `ColumnMappingPatch`; engine validates and applies; mapping is finalized before normalization.

### TableNormalizer (normalize)

**Responsibility:** Convert mapped rows into clean canonical rows:

* type coercion
* transforms
* validation issues with row + column references

### TableRenderer (render/write)

**Responsibility:** Write `NormalizedTable` into `output_worksheet` and return `TablePlacement`.

* renderer decides where to write (layout cursor)
* writes header + rows
* optionally creates an Excel “structured table” (future toggle)
* returns placement for hook styling/comments

### Hooks (extension points)

**Responsibility:** Provide safe points to:

* register styles / named styles
* configure sheets
* inspect extracted data
* patch mapping (LLM)
* style/comment cells after writing
* finalize workbook before save

---

## 4.4 Data model & coding (canonical types)

### 4.4.1 Origin and region

```python
# src/ade_engine/types/origin.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class TableOrigin:
    source_path: Path
    sheet_name: str
    sheet_index: int      # 0-based order of worksheets in workbook
    table_index: int      # 0-based order of detected tables in worksheet


@dataclass(frozen=True)
class TableRegion:
    # Excel-style coordinates (1-based)
    min_row: int
    max_row: int
    min_col: int
    max_col: int
```

### 4.4.2 Stage tables

```python
# src/ade_engine/types/tables.py
from dataclasses import dataclass
from typing import Any, Sequence, Optional

@dataclass(frozen=True)
class ExtractedTable:
    origin: TableOrigin
    region: TableRegion
    header: list[str]
    rows: list[list[Any]]

    def preview(self, n: int = 10) -> list[list[Any]]:
        return self.rows[:n]


@dataclass(frozen=True)
class ColumnMapping:
    # canonical columns
    fields: list["MappedField"]            # ordered
    passthrough: list["PassthroughField"]  # ordered, optional

    @property
    def output_header(self) -> list[str]:
        return [f.field for f in self.fields] + [p.output_name for p in self.passthrough]


@dataclass(frozen=True)
class MappedField:
    field: str
    source_col: int | None                # 0-based column index within extracted region
    source_header: str | None
    score: float | None                   # from detection/scoring


@dataclass(frozen=True)
class PassthroughField:
    source_col: int
    source_header: str
    output_name: str


@dataclass(frozen=True)
class MappedTable:
    origin: TableOrigin
    region: TableRegion
    mapping: ColumnMapping
    extracted: ExtractedTable

    # A “mapped view” (projection) to avoid copying
    # For simplicity in initial refactor, it can be materialized.
    header: list[str]
    rows: Sequence[Sequence[Any]]


@dataclass
class NormalizedTable:
    origin: TableOrigin
    region: TableRegion

    header: list[str]
    rows: list[list[Any]]

    issues: list["ValidationIssue"]
```

> **Implementation note:** `MappedTable.rows` SHOULD be a projection view (row plan) in the final implementation to reduce memory copying.

### 4.4.3 Mapping patch (LLM hook)

```python
# src/ade_engine/types/mapping.py
from dataclasses import dataclass

@dataclass(frozen=True)
class ColumnMappingPatch:
    """
    Change-set applied after initial mapping, before normalization.

    assign maps canonical field -> source column index (0-based, within extracted region).
    rename_passthrough maps source column index -> new output header name.
    drop_passthrough lists passthrough source columns to omit from output.
    """
    assign: dict[str, int] | None = None
    rename_passthrough: dict[int, str] | None = None
    drop_passthrough: set[int] | None = None
```

**Patch validation rules:**

* assigned canonical field must exist in manifest
* assigned source column must be within extracted header bounds
* no two canonical fields may point to the same `source_col`
* dropping a passthrough col that’s not passthrough is a no-op or error (choose one; recommend **error** for predictability)
* renaming passthrough col must refer to an existing passthrough col

### 4.4.4 Placement + view (openpyxl-native range access)

```python
# src/ade_engine/types/origin.py (or contexts.py)
from dataclasses import dataclass
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.worksheet.cell_range import CellRange

@dataclass(frozen=True)
class TablePlacement:
    worksheet: Worksheet
    cell_range: CellRange
    origin: TableOrigin


@dataclass(frozen=True)
class TableView:
    worksheet: Worksheet
    cell_range: CellRange

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return self.cell_range.bounds  # (min_col, min_row, max_col, max_row) in openpyxl order

    def header_cells(self):
        min_col, min_row, max_col, _ = self.cell_range.bounds
        return [self.worksheet.cell(row=min_row, column=c) for c in range(min_col, max_col + 1)]

    def iter_data_rows(self):
        min_col, min_row, max_col, max_row = self.cell_range.bounds
        for r in range(min_row + 1, max_row + 1):
            yield [self.worksheet.cell(row=r, column=c) for c in range(min_col, max_col + 1)]
```

---

## 4.5 Hooks: interface, contexts, and call order

### 4.5.1 Context objects (what hooks receive)

```python
# src/ade_engine/types/contexts.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

@dataclass
class RunContext:
    source_path: Path
    output_path: Path
    manifest: "Manifest"

    source_workbook: openpyxl.Workbook
    output_workbook: openpyxl.Workbook

    # a simple scratchpad users can stash state in
    state: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorksheetContext:
    run: RunContext
    sheet_index: int

    source_worksheet: Worksheet
    output_worksheet: Worksheet


@dataclass
class TableContext:
    sheet: WorksheetContext
    origin: TableOrigin
    region: TableRegion

    extracted: Optional[ExtractedTable] = None
    mapped: Optional[MappedTable] = None
    normalized: Optional[NormalizedTable] = None

    placement: Optional[TablePlacement] = None
    view: Optional[TableView] = None

    # set if on_table_mapped applies a patch
    mapping_patch: Optional[ColumnMappingPatch] = None
```

### 4.5.2 Hook protocol

```python
# src/ade_engine/hooks/protocol.py
from typing import Protocol, Optional

class ADEHooks(Protocol):
    def on_workbook_start(self, ctx: RunContext) -> None: ...
    def on_sheet_start(self, sheet_ctx: WorksheetContext) -> None: ...

    def on_table_detected(self, table_ctx: TableContext) -> None: ...

    # returns patch to update mapping (LLM workflow)
    def on_table_mapped(self, table_ctx: TableContext) -> Optional[ColumnMappingPatch]: ...

    # called after table is written; hooks can style/comment the output range
    def on_table_written(self, table_ctx: TableContext) -> None: ...

    def on_workbook_before_save(self, ctx: RunContext) -> None: ...
```

Config packages remain manifest-driven: `ade_config/manifest.json` lists hook modules using the stage names above (paths are relative to the `ade_config` package):

```json
"hooks": {
  "on_workbook_start": ["hooks.on_workbook_start"],
  "on_sheet_start": ["hooks.on_sheet_start"],
  "on_table_detected": ["hooks.on_table_detected"],
  "on_table_mapped": ["hooks.on_table_mapped"],
  "on_table_written": ["hooks.on_table_written"],
  "on_workbook_before_save": ["hooks.on_workbook_before_save"]
}
```

Each hook module keeps a keyword-only `run(**kwargs)` entrypoint (with `**_` for forward compatibility). The engine injects the contexts above: `run_ctx` for workbook-level calls, `sheet_ctx` for sheet-level calls, and `table_ctx` for table-level calls; `on_table_mapped` returns a `ColumnMappingPatch | None`, all other stages return `None`. Shared state remains available through `run_ctx.state` (reachable from `sheet_ctx.run` / `table_ctx.sheet.run`).

```python
# ade_config/hooks/on_table_mapped.py
def run(
    *,
    table_ctx: TableContext,
    run_ctx: RunContext,
    logger=None,
    **_,
) -> ColumnMappingPatch | None:
    ...
```

### 4.5.3 Hook call order (per workbook run)

1. `on_workbook_start(run_ctx)`
2. For each sheet:

   * `on_sheet_start(sheet_ctx)`
   * For each detected table (top-to-bottom):

     * extract table
     * `on_table_detected(table_ctx)`
     * map table
     * `patch = on_table_mapped(table_ctx)` (optional)
     * apply patch if provided (mapping finalized)
     * normalize
     * render/write into output worksheet → placement
     * `on_table_written(table_ctx)`
3. `on_workbook_before_save(run_ctx)`
4. `output_workbook.save(output_path)`

**Hook safety contract (document + tests):**

* Hooks may mutate **styles/comments/formats** freely.
* Hooks should not insert/delete rows/cols or create cells outside the returned `TablePlacement` unless they fully own the layout.
* Renderer placement is authoritative.

---

## 4.6 Key flows / pipelines (high-level run)

### 4.6.1 ADEngine.run() pseudocode

```python
# src/ade_engine/engine.py
import openpyxl
from openpyxl.worksheet.cell_range import CellRange
from ade_engine.types.contexts import RunContext, WorksheetContext, TableContext, TableView
from ade_engine.types.origin import TableOrigin, TablePlacement

class ADEngine:
    def __init__(self, detector, extractor, mapper, normalizer, renderer, hooks):
        self.detector = detector
        self.extractor = extractor
        self.mapper = mapper
        self.normalizer = normalizer
        self.renderer = renderer
        self.hooks = hooks

    def run(self, source_path, output_path, manifest):
        source_wb = openpyxl.load_workbook(source_path, data_only=True, read_only=True)
        output_wb = openpyxl.Workbook()
        # delete default sheet
        if output_wb.worksheets and output_wb.worksheets[0].title == "Sheet":
            output_wb.remove(output_wb.worksheets[0])

        run_ctx = RunContext(
            source_path=source_path,
            output_path=output_path,
            manifest=manifest,
            source_workbook=source_wb,
            output_workbook=output_wb,
        )
        self.hooks.on_workbook_start(run_ctx)

        for sheet_index, src_ws in enumerate(source_wb.worksheets):
            out_ws = output_wb.create_sheet(title=src_ws.title)
            sheet_ctx = WorksheetContext(
                run=run_ctx,
                sheet_index=sheet_index,
                source_worksheet=src_ws,
                output_worksheet=out_ws,
            )
            self.hooks.on_sheet_start(sheet_ctx)

            regions = self.detector.detect(src_ws)
            for table_index, region in enumerate(regions):
                origin = TableOrigin(
                    source_path=source_path,
                    sheet_name=src_ws.title,
                    sheet_index=sheet_index,
                    table_index=table_index,
                )
                table_ctx = TableContext(sheet=sheet_ctx, origin=origin, region=region)

                extracted = self.extractor.extract(src_ws, origin, region)
                table_ctx.extracted = extracted
                self.hooks.on_table_detected(table_ctx)

                mapped = self.mapper.map(extracted, manifest)
                table_ctx.mapped = mapped
                patch = self.hooks.on_table_mapped(table_ctx)
                if patch:
                    table_ctx.mapping_patch = patch
                    mapped = self.mapper.apply_patch(mapped, patch, manifest)
                    table_ctx.mapped = mapped

                normalized = self.normalizer.normalize(mapped, manifest)
                table_ctx.normalized = normalized

                placement = self.renderer.write_table(out_ws, normalized)
                table_ctx.placement = placement
                table_ctx.view = TableView(placement.worksheet, placement.cell_range)

                self.hooks.on_table_written(table_ctx)

        self.hooks.on_workbook_before_save(run_ctx)
        output_wb.save(output_path)
```

---

## 4.7 Renderer design (writing + placement)

### 4.7.1 Layout policy (simple default)

**Default:** Write each normalized table as:

* header row
* data rows
* one blank row separator between tables

This preserves table boundaries and order clearly.

```python
# src/ade_engine/render/layout.py
from dataclasses import dataclass

@dataclass
class SheetLayout:
    next_row: int = 1
    blank_rows_between_tables: int = 1
```

Renderer chooses a start row = `layout.next_row`, writes table, updates `layout.next_row = end_row + blank_rows + 1`.

### 4.7.2 Renderer signature

```python
# src/ade_engine/render/renderer.py
from openpyxl.worksheet.cell_range import CellRange
from ade_engine.types.origin import TablePlacement

class TableRenderer:
    def __init__(self, layout: SheetLayout | None = None):
        self.layout = layout or SheetLayout()

    def write_table(self, ws, table: NormalizedTable) -> TablePlacement:
        start_row = self.layout.next_row
        start_col = 1

        # write header
        for j, name in enumerate(table.header):
            ws.cell(row=start_row, column=start_col + j, value=name)

        # write rows
        for i, row in enumerate(table.rows, start=1):
            for j, value in enumerate(row):
                ws.cell(row=start_row + i, column=start_col + j, value=value)

        end_row = start_row + len(table.rows)
        end_col = start_col + len(table.header) - 1

        self.layout.next_row = end_row + self.layout.blank_rows_between_tables + 1
        rng = CellRange(min_col=start_col, min_row=start_row, max_col=end_col, max_row=end_row)

        return TablePlacement(worksheet=ws, cell_range=rng, origin=table.origin)
```

---

## 4.8 LLM-assisted mapping: how it fits elegantly

### Why `on_table_mapped` is the right hook

At this point you have:

* extracted header + sample rows (best prompt material)
* the initial mapping results
* explicit list of unmapped headers/passthrough columns

The hook returns a minimal `ColumnMappingPatch` (change-set), engine validates it, then proceeds.

### Recommended “prompt payload” exposed through `TableContext`

Hook has access to:

* `table_ctx.extracted.header`
* `table_ctx.extracted.preview(n=10)`
* `table_ctx.mapped.mapping.fields`
* `table_ctx.mapped.mapping.passthrough`

This is exactly what an LLM needs to decide “Header X is actually canonical field Y”.

---

## 5. Hook examples (what’s passed, how to mutate)

### 5.1 on_workbook_start(ctx): define named styles once

```python
from openpyxl.styles import NamedStyle, Font, Alignment, PatternFill

class MyHooks:
    def on_workbook_start(self, ctx):
        wb = ctx.output_workbook

        header = NamedStyle(name="ADE_Header")
        header.font = Font(bold=True)
        header.alignment = Alignment(horizontal="center")
        header.fill = PatternFill("solid", fgColor="FFDDEEFF")

        existing = {s.name for s in wb.named_styles}
        if header.name not in existing:
            wb.add_named_style(header)

    def on_sheet_start(self, sheet_ctx): ...
    def on_table_detected(self, table_ctx): ...
    def on_table_mapped(self, table_ctx): ...
    def on_table_written(self, table_ctx): ...
    def on_workbook_before_save(self, ctx): ...
```

What’s passed:

* `ctx.output_workbook` is a real openpyxl `Workbook`.

---

### 5.2 on_sheet_start(sheet_ctx): freeze panes, widths, sheet settings

```python
from openpyxl.utils import get_column_letter

class MyHooks:
    def on_sheet_start(self, sheet_ctx):
        ws = sheet_ctx.output_worksheet
        ws.freeze_panes = "A2"
        for col in range(1, 12):
            ws.column_dimensions[get_column_letter(col)].width = 18
```

What’s passed:

* `sheet_ctx.source_worksheet` (read-only worksheet)
* `sheet_ctx.output_worksheet` (editable worksheet)

---

### 5.3 on_table_detected(table_ctx): inspect extracted data, log, guard rules

```python
class MyHooks:
    def on_table_detected(self, table_ctx):
        origin = table_ctx.origin
        extracted = table_ctx.extracted
        print(f"Detected table {origin.table_index} on {origin.sheet_name}: {extracted.header}")
```

What’s passed:

* `table_ctx.region` describes bounds
* `table_ctx.extracted` contains raw header + rows

---

### 5.4 on_table_mapped(table_ctx): LLM-assisted mapping patch

```python
class MyHooks:
    def on_table_mapped(self, table_ctx):
        mapped = table_ctx.mapped
        extracted = table_ctx.extracted

        # Example: trivial heuristic “LLM stand-in”
        # If we see a passthrough column with header "Employee ID", map it to canonical "employee_id"
        passthrough_headers = {p.source_header.lower(): p.source_col for p in mapped.mapping.passthrough}
        if "employee id" in passthrough_headers:
            return ColumnMappingPatch(assign={"employee_id": passthrough_headers["employee id"]})

        return None
```

What’s passed:

* `table_ctx.mapped.mapping` includes canonical fields + passthrough columns
* return value: optional `ColumnMappingPatch`

---

### 5.5 on_table_written(table_ctx): style header row, add comments for issues

```python
from openpyxl.comments import Comment

class MyHooks:
    def on_table_written(self, table_ctx):
        view = table_ctx.view
        normalized = table_ctx.normalized
        if not view or not normalized:
            return

        # Style header
        for cell in view.header_cells():
            cell.style = "ADE_Header"

        # Add comments for validation issues
        header_index = {name: i for i, name in enumerate(normalized.header)}  # 0-based
        min_col, min_row, _, _ = view.cell_range.bounds

        for issue in normalized.issues:
            col_i = header_index.get(issue.field)
            if col_i is None:
                continue

            # issue.row_index is 0-based relative to first data row
            r = min_row + 1 + issue.row_index
            c = min_col + col_i
            cell = view.worksheet.cell(row=r, column=c)

            msg = f"{issue.code}: {issue.message}"
            cell.comment = Comment(msg, "ADE")
```

What’s passed:

* `table_ctx.placement` includes `Worksheet + CellRange`
* `table_ctx.view` makes it easy to stay inside the table range
* `table_ctx.normalized.issues` provides targets for comments/styling

---

### 5.6 on_workbook_before_save(ctx): final global adjustments (autofit)

```python
from openpyxl.utils import get_column_letter

class MyHooks:
    def on_workbook_before_save(self, ctx):
        wb = ctx.output_workbook
        for ws in wb.worksheets:
            for col_cells in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col_cells[0].column)
                for cell in col_cells:
                    if cell.value is not None:
                        max_len = max(max_len, len(str(cell.value)))
                if max_len:
                    ws.column_dimensions[col_letter].width = max_len + 2
```

---

## 6. Implementation notes for agents

### 6.1 Read/write settings (openpyxl)

* Default source load: `read_only=True, data_only=True` for speed.
* If future requirements need source comments/styles, add a config to load source non-read-only (more memory).

### 6.2 Efficiency principles (must follow)

* Create output workbook/sheets early (so hooks can configure them).
* Do **not** create output cells until renderer writes a table.
* `MappedTable.rows` should be a projection view (row-plan) in final implementation to avoid copying.

### 6.3 Hook safety conventions (document + test)

* It’s okay to style/comment cells anywhere.
* Avoid row/col insert/delete in hooks; renderer owns layout. (If needed later, add a “layout API” rather than raw sheet mutations.)

### 6.4 Structured Excel tables (optional future toggle)

Once `TablePlacement` exists, hooks (or renderer) can create an Excel “Table” object over that range, if desired. This is not required for this refactor but is a natural extension point.

---

## 7. Testing plan (rewrite everything to match new design)

### Unit tests

* detector detects correct `TableRegion` ordering
* mapper produces stable `ColumnMapping` for known headers
* patch validator rejects invalid patch (duplicates/out-of-range/unknown fields)
* normalizer emits `ValidationIssue` with correct row/field targeting
* renderer produces correct `CellRange` placement and writes correct values
* hook call order verified (spy hooks)

### Integration tests

* end-to-end: one workbook with multiple sheets & multiple tables per sheet

  * assert output workbook has same sheet order
  * assert each table written in order with blank row separation
  * assert `on_table_written` can apply style + comment and they persist in saved file

---

## 8. Documentation deliverables (rewrite)

* `docs/architecture.md`: the pipeline + terminology + diagrams
* `docs/hooks.md`: hook lifecycle + examples + dos/don’ts
* `docs/manifest.md`: Script API v3 manifest schema (unchanged columns/writer) + new hook stage names + examples (+ LLM patch workflows)
* `README.md`: quickstart, minimal example hook + run command

---

## 9. Open questions / decisions (lock now)

* **Table layout policy:** default is **header per table + blank row separator**.

  * Rationale: preserves boundaries and keeps logic simple.
* **Mapping patch behavior:** patch overrides initial mapping for specified fields; engine validates strictly; invalid patch fails fast.
* **Source workbook mode default:** `read_only=True` (fast). Opt-in to richer source access later.

> **Agent instruction:** If any of these decisions change during implementation, update this workpackage first.

# IO and Table Detection

This document describes how the ADE engine:

1. Discovers **source files** (CSV/XLSX),
2. Streams **rows** from those files in a memory‑friendly way, and
3. Uses **row detectors** from `ade_config` to turn raw sheets into `RawTable`
   objects that feed the mapping stage.

It assumes you’ve read:

- `README.md` (high‑level architecture)
- `01-engine-runtime.md`
- `02-config-and-manifest.md`

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

This vocabulary is used consistently in IO and detection docs—avoid synonyms
like “input file” unless referring to CLI flag names.

Relevant modules:

- `io.py` — low‑level file and sheet IO.
- `pipeline/extract.py` — table detection over streamed rows.
- `ade_config.row_detectors` — config‑side detection scripts.

---

## 1. Responsibilities and constraints

The IO + extract layer has three core responsibilities:

1. **Turn a `RunRequest` into a deterministic sequence of source files.**
2. **Stream rows** from CSV/XLSX without loading whole workbooks into memory.
3. **Locate tables** in each sheet by running row detectors and emitting
   `RawTable` objects.

Design constraints:

- **Run-scoped, not backend-orchestration aware** — everything is path‑based.
- **Streaming‑friendly** — large workbooks should not require large amounts
  of memory.
- **Config‑driven** — row detectors are provided by `ade_config`, not hard‑coded.
- **Predictable ordering** — given the same inputs and config, detection is
  deterministic.

The output of this layer is a list of `RawTable` objects that fully describe
each detected table, including header row, data rows, and location metadata.

---

## 2. From RunRequest to source files

### 2.1 Sources: `input_files` vs `input_dir`

`RunRequest` offers two ways to specify inputs:

- `input_files: Sequence[Path]`  
  Explicit list of source files to process.

- `input_dir: Path`  
  A directory to scan for source files.

Invariants enforced upstream (in `Engine.run`):

- Exactly **one** of `input_files` or `input_dir` must be set.
- Paths are normalized to absolute paths before use.

### 2.2 File discovery

When `input_dir` is provided, `io.list_input_files` is used to discover files:

```python
def list_input_files(input_dir: Path) -> list[Path]:
    """
    Return a sorted list of CSV/XLSX files under input_dir.

    - Ignores hidden files and directories (implementation detail).
    - Filters by extension (.csv, .xlsx).
    - Returns absolute Paths in a deterministic order.
    """
````

Characteristics:

* **Deterministic order** — ensures reproducible results and artifact output.
* **Simple filter** — engine currently supports `.csv` and `.xlsx` only.
* Discovery is **shallow vs recursive** based on implementation; whatever we
  choose should be documented and stable.

When `input_files` is provided, `list_input_files` is skipped; the engine uses
the given list as‑is (after normalization).

### 2.3 File type classification

Each discovered input is classified by extension:

* `.csv` → **CSV file**
* `.xlsx`, `.xlsm`, `.xltx`, `.xltm` → **Excel Open XML** (handled by openpyxl)

Unsupported extensions are rejected early as **input errors**
(e.g., “File `foo.xls` has unsupported extension `.xls`”). ADE does not use
any legacy Excel readers; only 2010+ Open XML formats are supported via
openpyxl.

---

## 3. CSV IO

### 3.1 Streaming rows from CSV

CSV files are treated as a single logical sheet.

`io.py` provides a helper similar to:

```python
def iter_csv_rows(path: Path) -> Iterable[tuple[int, list]]:
    """
    Stream (row_index, row_values) from a CSV file.

    - row_index is 1-based.
    - row_values is a list of Python primitives (usually strings).
    - Uses UTF-8 with BOM tolerance by default.
    """
```

Behavior:

* Uses `csv.reader` (or equivalent) to iterate rows.
* Keeps only one row in memory at a time.
* Passes raw values straight into row detectors; further normalization can
  happen in detectors or later stages if needed.

### 3.2 CSV and tables

By default, the engine assumes:

* **One potential table per CSV file.**

Row detectors still decide where the header and data blocks are, but the engine
does not try to find multiple independent tables in a single CSV. That is a
possible future extension.

---

## 4. XLSX IO

### 4.1 Workbook loading

XLSX files are opened in streaming mode using `openpyxl`:

```python
from openpyxl import load_workbook

def open_workbook(path: Path):
    return load_workbook(
        filename=path,
        read_only=True,
        data_only=True,
    )
```

Design goals:

* Never load entire workbook into memory when not necessary.
* Always work in terms of standard Python primitives:
  strings, numbers, booleans, `None`.
* **Read‑only consequences** — `read_only=True` yields a streaming worksheet;
  some APIs like `iter_cols()` aren’t available. Use `iter_rows()`/`.rows`.
  Charts/images and other rich objects are ignored by design.

### 4.2 Sheet selection

The mapping from a workbook to sheets is:

* If `RunRequest.input_sheets` is **not** provided:

  * Process all visible sheets in workbook order.
* If `input_sheets` **is** provided:

  * Restrict to the named sheets.
  * Missing sheet names are treated as a **hard error** (“Worksheet `Foo`
    not found in `input.xlsx`”).

This mapping is applied per workbook, so different workbooks can have different
sheet sets.

### 4.3 Streaming rows from sheets

`io.py` provides a helper like:

```python
def iter_sheet_rows(path: Path, sheet_name: str) -> Iterable[tuple[int, list]]:
    """
    Stream (row_index, row_values) from a sheet in an XLSX file.

    - row_index is 1-based.
    - row_values is a list of simple Python values (str, float, bool, datetime, None, ...).
    """
```

Typical logic:

* Use `worksheet.iter_rows(values_only=True)` under the hood.
* Normalize values:

  * Excel blanks → `None`.
  * Numbers → `int`/`float`.
  * Dates/times → `datetime` objects per openpyxl’s formatting.
  * Formulas → cached values via `data_only=True` (never the formula string).

The exact normalization strategy (e.g., whether to keep `None` or coerce to
`""`) should be stable and documented; any changes must be coordinated with
detectors and config authors.

Detectors and downstream scripts should expect native Python types (including
`datetime`) from openpyxl, not pre-stringified cell values.

### 4.4 Formula cells and `data_only=True`

Workbooks are opened with `data_only=True`, so openpyxl returns **cached
formula results**, not the formula strings. openpyxl does **not** evaluate
formulas itself; if the workbook was not recalculated and saved by Excel (or
another tool that populates cached values), formula cells surface as `None`.
The engine treats these as missing values and does not attempt to recompute
formulas.

---

## 5. Row detectors and table detection

### 5.1 Role of row detectors

Row detectors live in `ade_config.row_detectors` and are responsible for
identifying:

* **header rows** — where column names live,
* **data rows** — the main body of the table.

The engine **does not** hard‑code any notion of a header row or data start/end;
it relies entirely on detector scores and a small set of heuristics.

### 5.2 Detector API (config side)

A typical row detector has this shape:

```python
def detect_header_or_data(
    *,
    run: RunContext,             # RunContext (config-facing view of the run)
    state: dict,
    row_index: int,      # 1-based index within the sheet
    row_values: list,    # raw cell values for this row
    manifest,            # ManifestContext
    logger,
) -> dict:
    """
    Return a dict with per-label scores.

    Example:
        {"scores": {"header": 0.7, "data": 0.1}}
    """
```

Conventions:

* `run` is read‑only from the config’s perspective (it is a `RunContext`).
* `state` is a per‑run dict that detectors may use to coordinate across rows.
* `manifest` provides config‑level context (schema, defaults, writer, fields).
* `logger` allows emitting notes and telemetry if needed.
* Functions should accept `**_` to tolerate new parameters over time.

Return contract:

* A dict containing a `"scores"` key:

  * `"scores"` is a map from labels to floats.
  * Typical labels are `"header"` and `"data"`, but detectors may emit more
    specialized labels as long as the engine knows how to interpret them.

### 5.3 Aggregation and scoring

For each row of each sheet:

1. Engine calls all row detectors with that row.
2. Each detector returns a `"scores"` map.
3. Engine aggregates scores by label (e.g., `"header"`, `"data"`) by
   **summing contributions**.

The result is a per‑row summary like:

```python
RowScore = {
    "row_index": 12,
    "header_score": 0.85,
    "data_score": 0.15,
}
```

Exact thresholds and label names are implementation details but should be
documented in code comments and tests.

### 5.4 Heuristics for deciding table boundaries (multiple per sheet)

Using row scores, `pipeline/extract.py` can find **multiple logical tables per sheet**. The
baseline flow:

1. Scan rows top‑down, looking for a **header candidate** above a threshold.
   * The first qualifying header starts **Table 0** on that sheet.
2. From that header, accumulate contiguous **data rows** above a data threshold.
   * Trailing low‑signal rows are trimmed.
3. After a data block ends (or after trimming), continue scanning **below the last data row**
   for the next header candidate. If found, start **Table 1**, and repeat.
4. Stop when the end of the sheet is reached or no further header candidates pass the threshold.
5. If no header/data block is found at all, the sheet produces no `RawTable` and the engine
   logs an informative diagnostic.

CSV inputs follow the same logic but have a single implicit sheet.

Heuristics (thresholds, minimum row counts, required gaps between tables) are tunable in code
and may be influenced by manifest defaults (e.g., minimum data rows). The ordering of tables per
sheet is deterministic: top‑to‑bottom as discovered.

---

## 6. RawTable model

Once a table is identified, the engine materializes a `RawTable` dataclass
(see `types.py`), conceptually:

```python
@dataclass
class RawTable:
    source_file: Path
    source_sheet: str | None
    table_index: int              # 0-based ordinal within the sheet
    header_row: list[str]          # normalized header cells
    data_rows: list[list[Any]]     # all data rows for the table
    header_row_index: int          # 1-based row index of header in the sheet
    first_data_row_index: int      # 1-based row index of first data row
    last_data_row_index: int       # 1-based row index of last data row
```

Details:

* `source_file` — absolute path to the source file.
* `source_sheet` — sheet name for XLSX; `None` for CSV.
* `table_index` — 0-based order in which tables were detected within the sheet.
* `header_row` — header cells normalized to strings (e.g. `None` → `""`).
* `data_rows` — full set of rows between `first_data_row_index` and
  `last_data_row_index` that the algorithm considers part of the table.
* Indices are **1‑based** and correspond to original sheet row numbers; this
  is important for traceability and artifact reporting.

`RawTable` is the only table‑level type passed into column mapping.

---

## 7. Integration with artifact and telemetry

### 7.1 Artifact entries

During extraction, the engine records basic information in the artifact
(via `ArtifactSink`), such as:

* For each table:

  * `input_file`
  * `input_sheet`
  * `header.row_index`
  * `header.cells`
  * row counts, etc.

This allows later inspection of what the engine believed the table shape was,
even before mapping/normalization.

### 7.2 Telemetry events

`PipelineLogger` is available during extraction and may emit events like:

* `pipeline_transition` with phase `"EXTRACTING"`.
* `table_completed` for each table once it is fully mapped/validated.
* `note` for human-readable breadcrumbs.
* Custom `logger.event(...)` payloads from configs if you want finer-grained
  signals (e.g. per-row validation issues).

These events are written to `events.ndjson` and can be consumed by the ADE
backend for realtime progress indicators or metrics.

---

## 8. Edge cases and error handling

### 8.1 Empty files / sheets

* If a file or sheet yields no rows at all:

  * Engine records a note and skip it.
  * No `RawTable` is created.
* If detectors cannot identify a header/data region:

  * Engine may:

    * Treat it as “no tables found on sheet,” and/or
    * Emit a warning in artifact/telemetry.

Policies should be consistent and covered by tests.

### 8.2 Missing or invalid sheets

* If a sheet name listed in `input_sheets` does not exist:

  * The run fails with a clear error.
  * Artifact indicates failure cause under `run.error`.
* If a workbook cannot be opened (corrupt file):

  * The run fails similarly, with an explicit “could not read file” error.

### 8.3 Multiple tables per sheet

A sheet can yield multiple `RawTable` objects, each with its own header/data
region. Table detection logic can segment by gaps and continue scanning for
additional tables within the same sheet.

---

## 9. Summary

The IO and table detection layer is responsible for:

1. Turning a `RunRequest` into a **deterministic list of source files**.
2. Streaming **rows** from CSV/XLSX in a memory‑conscious way.
3. Using **config‑provided row detectors** to identify table boundaries and
   emit `RawTable` objects with precise sheet/row metadata.

Everything beyond this point — column mapping, normalization, artifact detail —
is layered on top of these `RawTable`s. If extraction is correct and well
instrumented, the rest of the pipeline can reliably reason about what the
engine “saw” in the original spreadsheets.

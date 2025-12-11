export type AdeFunctionKind =
  | "row_detector"
  | "column_detector"
  | "column_transform"
  | "column_validator"
  | "hook_workbook_start"
  | "hook_sheet_start"
  | "hook_table_detected"
  | "hook_table_mapped"
  | "hook_table_written"
  | "hook_workbook_before_save";

export interface AdeFunctionSpec {
  kind: AdeFunctionKind;
  name: string;
  label: string;
  signature: string;
  doc: string;
  snippet: string;
  parameters: string[];
}

const rowDetectorSpec: AdeFunctionSpec = {
  kind: "row_detector",
  name: "detect_*",
  label: "ADE: row detector (detect_*)",
  signature: [
    "def detect_*(",
    "    *,",
    "    row_index: int,",
    "    row_values: list,",
    "    sheet_name: str | None,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> dict[str, float] | None:",
  ].join("\n"),
  doc: "Row detector entrypoint: vote for row kinds (e.g., header vs data). Return a mapping of RowKind→score deltas or None.",
  snippet: `
def detect_\${2:name}(
    *,
    row_index: int,
    row_values: list,
    sheet_name: str | None,
    metadata: dict | None,
    state: dict,
    input_file_name: str | None,
    logger,
    **_,
) -> dict[str, float] | None:
    """\${3:Explain what this detector scores.}"""
    values = row_values or []
    non_empty = [v for v in values if v not in (None, \"\") and not (isinstance(v, str) and not v.strip())]
    density = len(non_empty) / max(len(values), 1) if values else 0.0
    score = min(1.0, density)
    return {"data": score, "header": -score * 0.2}
`.trim(),
  parameters: ["row_index", "row_values", "sheet_name", "metadata", "state", "input_file_name", "logger"],
};

const columnDetectorSpec: AdeFunctionSpec = {
  kind: "column_detector",
  name: "detect_*",
  label: "ADE: column detector (detect_*)",
  signature: [
    "def detect_*(",
    "    *,",
    "    column_index: int,",
    "    header,",
    "    values,",
    "    values_sample,",
    "    sheet_name: str | None,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> dict[str, float] | None:",
  ].join("\n"),
  doc: "Column detector entrypoint: score how likely the current raw column maps to a canonical field.",
  snippet: `
def detect_\${1:value_shape}(
    *,
    column_index: int,
    header,
    values,
    values_sample,
    sheet_name: str | None,
    metadata: dict | None,
    state: dict,
    input_file_name: str | None,
    logger,
    **_,
) -> dict[str, float] | None:
    """\${2:Describe your heuristic for this field.}"""
    target_field = "\${3:field_name}"
    header_text = "" if header is None else str(header).strip().lower()
    if not header_text:
        return None
    if target_field.replace("_", " ") in header_text:
        return {target_field: 1.0}
    return None
`.trim(),
  parameters: [
    "column_index",
    "header",
    "values",
    "values_sample",
    "sheet_name",
    "metadata",
    "state",
    "input_file_name",
    "logger",
  ],
};

const columnTransformSpec: AdeFunctionSpec = {
  kind: "column_transform",
  name: "transform",
  label: "ADE: column transform",
  signature: [
    "def transform(",
    "    *,",
    "    field_name: str,",
    "    values,",
    "    mapping,",
    "    state: dict,",
    "    metadata: dict | None,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> list[dict]:",
  ].join("\n"),
  doc: "Column transform: normalize column values and emit row-indexed results. Return a list of {row_index, value}.",
  snippet: `
def transform(
    *,
    field_name: str,
    values,
    mapping,
    state: dict,
    metadata: dict | None,
    input_file_name: str | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Normalize or expand the values for this column.}"""
    results: list[dict] = []
    for idx, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        normalized = text.title() if text else None
        results.append({"row_index": idx, "value": {field_name: normalized}})
    return results
`.trim(),
  parameters: ["field_name", "values", "mapping", "state", "metadata", "input_file_name", "logger"],
};

const columnValidatorSpec: AdeFunctionSpec = {
  kind: "column_validator",
  name: "validate",
  label: "ADE: column validator",
  signature: [
    "def validate(",
    "    *,",
    "    field_name: str,",
    "    values,",
    "    mapping,",
    "    state: dict,",
    "    metadata: dict | None,",
    "    column_index: int,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> list[dict]:",
  ].join("\n"),
  doc: "Column validator: emit structured issues for a column. Return a list of {row_index, message, ...}.",
  snippet: `
def validate(
    *,
    field_name: str,
    values,
    mapping,
    state: dict,
    metadata: dict | None,
    column_index: int,
    input_file_name: str | None,
    logger,
    **_,
) -> list[dict]:
    """\${1:Return validation issues for this column.}"""
    issues: list[dict] = []
    for idx, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        if metadata and metadata.get("required") and not text:
            issues.append({"row_index": idx, "message": f"{field_name} is required"})
        # Add custom checks here (e.g., regex, enum membership).
    return issues
`.trim(),
  parameters: [
    "field_name",
    "values",
    "mapping",
    "state",
    "metadata",
    "column_index",
    "input_file_name",
    "logger",
  ],
};

const hookWorkbookStartSpec: AdeFunctionSpec = {
  kind: "hook_workbook_start",
  name: "on_workbook_start",
  label: "ADE hook: on_workbook_start",
  signature: [
    "def on_workbook_start(",
    "    *,",
    "    hook_name,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    workbook,",
    "    sheet,",
    "    table,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Called once per workbook before any sheets/tables are processed.",
  snippet: `
def on_workbook_start(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Seed shared state or log workbook info.}"""
    state.setdefault("notes", [])
    if logger:
        logger.info("workbook start: %s", input_file_name or "")
    return None
`.trim(),
  parameters: ["hook_name", "metadata", "state", "workbook", "sheet", "table", "input_file_name", "logger"],
};

const hookSheetStartSpec: AdeFunctionSpec = {
  kind: "hook_sheet_start",
  name: "on_sheet_start",
  label: "ADE hook: on_sheet_start",
  signature: [
    "def on_sheet_start(",
    "    *,",
    "    hook_name,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    workbook,",
    "    sheet,",
    "    table,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Called when a sheet is selected for processing (before detectors run).",
  snippet: `
def on_sheet_start(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Sheet-level logging or state init.}"""
    if logger and sheet:
        logger.info("sheet start: %s", getattr(sheet, "title", ""))
    return None
`.trim(),
  parameters: ["hook_name", "metadata", "state", "workbook", "sheet", "table", "input_file_name", "logger"],
};

const hookTableDetectedSpec: AdeFunctionSpec = {
  kind: "hook_table_detected",
  name: "on_table_detected",
  label: "ADE hook: on_table_detected",
  signature: [
    "def on_table_detected(",
    "    *,",
    "    hook_name,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    workbook,",
    "    sheet,",
    "    table,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Called after a table is detected. Inspect table metadata or log.",
  snippet: `
def on_table_detected(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Log detection details or tweak state.}"""
    if logger and table:
        logger.info("table detected: sheet=%s header_row=%s", getattr(table, "sheet_name", ""), getattr(table, "header_row_index", None))
    return None
`.trim(),
  parameters: ["hook_name", "metadata", "state", "workbook", "sheet", "table", "input_file_name", "logger"],
};

const hookTableMappedSpec: AdeFunctionSpec = {
  kind: "hook_table_mapped",
  name: "on_table_mapped",
  label: "ADE hook: on_table_mapped",
  signature: [
    "def on_table_mapped(",
    "    *,",
    "    hook_name,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    workbook,",
    "    sheet,",
    "    table,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> dict | None:",
  ].join("\n"),
  doc: "Called after mapping; return a ColumnMappingPatch or None.",
  snippet: `
def on_table_mapped(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> dict | None:
    """\${1:Propose mapping tweaks or log mapped columns.}"""
    if logger and table:
        mapped = [col.field_name for col in getattr(table, "mapped_columns", [])]
        logger.info("table mapped fields=%s", mapped)
    return None
`.trim(),
  parameters: ["hook_name", "metadata", "state", "workbook", "sheet", "table", "input_file_name", "logger"],
};

const hookTableWrittenSpec: AdeFunctionSpec = {
  kind: "hook_table_written",
  name: "on_table_written",
  label: "ADE hook: on_table_written",
  signature: [
    "def on_table_written(",
    "    *,",
    "    hook_name,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    workbook,",
    "    sheet,",
    "    table,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Called after a table is written to the output workbook.",
  snippet: `
def on_table_written(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Finalize sheet formatting or log counts.}"""
    if logger and table:
        logger.info("table written rows=%s", len(getattr(table, "rows", []) or []))
    return None
`.trim(),
  parameters: ["hook_name", "metadata", "state", "workbook", "sheet", "table", "input_file_name", "logger"],
};

const hookWorkbookBeforeSaveSpec: AdeFunctionSpec = {
  kind: "hook_workbook_before_save",
  name: "on_workbook_before_save",
  label: "ADE hook: on_workbook_before_save",
  signature: [
    "def on_workbook_before_save(",
    "    *,",
    "    hook_name,",
    "    metadata: dict | None,",
    "    state: dict,",
    "    workbook,",
    "    sheet,",
    "    table,",
    "    input_file_name: str | None,",
    "    logger,",
    "    **_,",
    ") -> None:",
  ].join("\n"),
  doc: "Called once before the output workbook is saved to disk.",
  snippet: `
def on_workbook_before_save(
    *,
    hook_name,
    metadata: dict | None,
    state: dict,
    workbook,
    sheet,
    table,
    input_file_name: str | None,
    logger,
    **_,
) -> None:
    """\${1:Style workbook or attach summaries before save.}"""
    if logger:
        logger.info("workbook before save: %s", input_file_name or "")
    return None
`.trim(),
  parameters: ["hook_name", "metadata", "state", "workbook", "sheet", "table", "input_file_name", "logger"],
};

export const ADE_FUNCTIONS: AdeFunctionSpec[] = [
  rowDetectorSpec,
  columnDetectorSpec,
  columnTransformSpec,
  columnValidatorSpec,
  hookWorkbookStartSpec,
  hookSheetStartSpec,
  hookTableDetectedSpec,
  hookTableMappedSpec,
  hookTableWrittenSpec,
  hookWorkbookBeforeSaveSpec,
];

export type AdeFileScope = "any";

const hookSpecsByName = new Map<string, AdeFunctionSpec>([
  [hookWorkbookStartSpec.name, hookWorkbookStartSpec],
  [hookSheetStartSpec.name, hookSheetStartSpec],
  [hookTableDetectedSpec.name, hookTableDetectedSpec],
  [hookTableMappedSpec.name, hookTableMappedSpec],
  [hookTableWrittenSpec.name, hookTableWrittenSpec],
  [hookWorkbookBeforeSaveSpec.name, hookWorkbookBeforeSaveSpec],
]);

export function getHoverSpec(word: string, _filePath?: string): AdeFunctionSpec | undefined {
  if (!word) {
    return undefined;
  }
  if (word.startsWith("detect_")) {
    return columnDetectorSpec; // default to column shape; row users can still insert snippets
  }
  if (word === columnTransformSpec.name) {
    return columnTransformSpec;
  }
  if (word === columnValidatorSpec.name) {
    return columnValidatorSpec;
  }
  return hookSpecsByName.get(word);
}

export function getSnippetSpecs(_filePath?: string): AdeFunctionSpec[] {
  return ADE_FUNCTIONS;
}

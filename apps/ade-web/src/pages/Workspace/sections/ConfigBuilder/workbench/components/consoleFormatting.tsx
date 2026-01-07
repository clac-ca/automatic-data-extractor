import type { ReactElement } from "react";
import type { WorkbenchConsoleLine } from "../types";

export function resolveSeverity(level: WorkbenchConsoleLine["level"] | "all"): number {
  if (level === "debug") return 0;
  if (level === "error") return 3;
  if (level === "warning") return 2;
  if (level === "success") return 1;
  if (level === "info") return 1;
  return 0;
}

export function renderConsoleLine(line: WorkbenchConsoleLine) {
  const raw = line.raw;
  if (raw && typeof raw === "object") {
    const formatted = formatEventRecord(raw as Record<string, unknown>);
    if (formatted) {
      return formatted;
    }
  }

  return renderPlainText(line.message);
}

export function formatConsoleLineNdjson(line: WorkbenchConsoleLine): string | null {
  const raw = line.raw;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  try {
    return JSON.stringify(raw);
  } catch {
    return null;
  }
}

function safeParseJson(value: string) {
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

function renderPlainText(message: string) {
  if (message.includes("\n")) {
    const lines = message.split(/\r?\n/);
    const [firstLine, ...rest] = lines;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{firstLine || " "}</span>
        {rest.length > 0 ? (
          <pre className="whitespace-pre-wrap break-words border-l border-border pl-3 text-[12px] leading-snug text-muted-foreground">
            {rest.join("\n")}
          </pre>
        ) : null}
      </div>
    );
  }

  const parsed = safeParseJson(message);
  if (!parsed) {
    return message;
  }

  const pretty = JSON.stringify(parsed, null, 2);
  return (
    <pre className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-foreground">
      {highlightJson(pretty)}
    </pre>
  );
}

function highlightJson(text: string) {
  const regex =
    /("(?:\\.|[^"])*"(?=:)|"(?:\\.|[^"])*")|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|\b(true|false|null)\b/g;
  const parts: Array<string | ReactElement> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const className = match[1]
      ? "text-info-300"
      : match[2]
        ? "text-warning-300"
        : "text-danger-300";
    parts.push(
      <span key={`json-${key++}`} className={className}>
        {token}
      </span>,
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

function formatEventRecord(event: Record<string, unknown>) {
  const name = typeof event.event === "string" ? event.event : "";
  if (!name) return null;

  const level = typeof event.level === "string" ? event.level.toLowerCase() : "";
  const message = typeof event.message === "string" ? event.message : "";
  const data = event.data && typeof event.data === "object" ? (event.data as Record<string, unknown>) : {};

  if (name === "console.line") {
    const text = typeof data.message === "string" ? data.message : message;
    return <span className="break-words">{text || " "}</span>;
  }

  if (name === "engine.log") {
    const parsed = parseConfigHook(message);
    return <span className="break-words">{parsed.text || " "}</span>;
  }

  if (name.startsWith("environment.") || name.startsWith("run.")) {
    const status = typeof data.status === "string" ? data.status : undefined;
    const reason = typeof data.reason === "string" ? data.reason : undefined;
    const phase = typeof data.phase === "string" ? data.phase : undefined;
    const phaseMessage = typeof data.message === "string" ? data.message : undefined;

    const formatDuration = (valueMs: number | undefined) => {
      if (!valueMs || valueMs < 0) return "";
      if (valueMs < 1000) return `${Math.round(valueMs)} ms`;
      if (valueMs < 60_000) return `${(valueMs / 1000).toFixed(1)} s`;
      const minutes = Math.floor(valueMs / 60_000);
      const seconds = Math.round((valueMs % 60_000) / 1000);
      return `${minutes}m ${seconds}s`;
    };

    if (name === "environment.start") {
      return <span className="break-words">{`Environment build started${reason ? ` (${reason})` : ""}`}</span>;
    }
    if (name === "environment.complete") {
      return <span className="break-words">{`Environment ${status ?? "ready"}`}</span>;
    }
    if (name === "environment.failed") {
      return <span className="break-words">Environment failed</span>;
    }

    if (name === "run.queued") {
      const mode = typeof data.mode === "string" ? data.mode : undefined;
      return <span className="break-words">{`Run queued${mode ? ` (${mode})` : ""}`}</span>;
    }
    if (name === "run.start") {
      const mode = typeof data.mode === "string" ? data.mode : undefined;
      return <span className="break-words">{`Run started${mode ? ` (${mode})` : ""}`}</span>;
    }
    if (name === "run.complete") {
      const execution = data.execution && typeof data.execution === "object" ? (data.execution as Record<string, unknown>) : {};
      const durationMs = typeof execution.duration_ms === "number" ? execution.duration_ms : undefined;
      const suffix = durationMs ? ` · ${formatDuration(durationMs)}` : "";
      return <span className="break-words">{`Run ${status ?? "completed"}${suffix}`}</span>;
    }

    if (message.trim()) {
      return <span className="break-words">{message}</span>;
    }

    // Default: keep it compact but readable.
    if (name.startsWith("environment.")) {
      return <span className="break-words">{phaseMessage || phase || status || name}</span>;
    }
    return <span className="break-words">{status || name}</span>;
  }

  if (name === "engine.config.loaded") {
    const pkgRaw = asString(data.config_package) ?? asString(data.config_package_name);
    const entry = asString(data.entrypoint);
    const fieldsCount = Array.isArray(data.fields) ? data.fields.length : undefined;
    const settings = asRecord(data.settings);
    const logFormat = asString(settings?.log_format);
    const logLevel = typeof settings?.log_level === "number" ? settings.log_level : undefined;

    const pkg = pkgRaw ? basename(pkgRaw) : undefined;
    const parts = [
      "Config loaded",
      entry ? `entry=${entry}` : null,
      typeof fieldsCount === "number" ? `fields=${fieldsCount}` : null,
      logFormat ? `log=${logFormat}${typeof logLevel === "number" ? `(${logLevel})` : ""}` : null,
      pkg && pkg !== "src" ? pkg : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.settings.effective") {
    const settings = asRecord(data.settings);
    if (!settings) {
      return <span className="break-words">Settings (effective)</span>;
    }
    const logFormat = asString(settings.log_format);
    const logLevel = typeof settings.log_level === "number" ? settings.log_level : undefined;
    const emptyRows = typeof settings.max_empty_rows_run === "number" ? settings.max_empty_rows_run : undefined;
    const emptyCols = typeof settings.max_empty_cols_run === "number" ? settings.max_empty_cols_run : undefined;
    const unmappedPrefix = asString(settings.unmapped_prefix);

    const parts = [
      "Settings",
      logFormat ? `log=${logFormat}${typeof logLevel === "number" ? `(${logLevel})` : ""}` : null,
      unmappedPrefix ? `unmapped=${unmappedPrefix}` : null,
      typeof emptyRows === "number" ? `maxEmptyRows=${emptyRows}` : null,
      typeof emptyCols === "number" ? `maxEmptyCols=${emptyCols}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.hook.start" || name === "engine.hook.end") {
    const hookName = asString(data.hook_name) ?? asString(data.hook);
    const verb = name.endsWith(".start") ? "start" : "end";
    return <span className="break-words">{hookName ? `Hook ${hookName} · ${verb}` : `Hook · ${verb}`}</span>;
  }

  if (name === "engine.run.started") {
    const inputFile = asString(data.input_file);
    const configPackage = asString(data.config_package);
    const parts = [
      "Run started",
      inputFile ? basename(inputFile) : null,
      configPackage ? `config=${basename(configPackage)}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.run.planned") {
    const outputFile = asString(data.output_file);
    const logsFile = asString(data.logs_file);
    const parts = [
      "Run planned",
      outputFile ? `output=${basename(outputFile)}` : null,
      logsFile ? `logs=${basename(logsFile)}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.run.completed") {
    const execution = asRecord(data.execution) ?? {};
    const evaluation = asRecord(data.evaluation) ?? {};
    const counts = asRecord(data.counts) ?? {};

    const status = asString(execution.status);
    const outcome = asString(evaluation.outcome);
    const durationMs = typeof execution.duration_ms === "number" ? execution.duration_ms : undefined;
    const tables = typeof counts.tables === "number" ? counts.tables : undefined;

    const parts = [
      "Run completed",
      status ? status : null,
      outcome ? `outcome=${outcome}` : null,
      typeof tables === "number" ? `tables=${tables}` : null,
      typeof durationMs === "number" ? `${Math.round(durationMs)}ms` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.workbook.started") {
    const sheetCount = typeof data.sheet_count === "number" ? data.sheet_count : undefined;
    return <span className="break-words">{`Workbook start${typeof sheetCount === "number" ? ` · sheets=${sheetCount}` : ""}`}</span>;
  }

  if (name === "engine.sheet.started") {
    const sheetName = asString(data.sheet_name);
    const sheetIndex = typeof data.sheet_index === "number" ? data.sheet_index + 1 : undefined;
    const parts = ["Sheet start", sheetName ? sheetName : null, typeof sheetIndex === "number" ? `#${sheetIndex}` : null].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.sheet.tables_detected") {
    const sheet = asString(data.sheet_name);
    const count = typeof data.table_count === "number" ? data.table_count : undefined;
    const rows = typeof data.row_count === "number" ? data.row_count : undefined;
    const parts = [
      sheet ? sheet : "Sheet",
      typeof count === "number" ? `tables=${count}` : null,
      typeof rows === "number" ? `rows=${rows}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.table.detected") {
    const sheet = asString(data.sheet_name);
    const tableIdx = typeof data.table_index === "number" ? data.table_index + 1 : undefined;
    const rows = typeof data.row_count === "number" ? data.row_count : undefined;
    const cols = typeof data.column_count === "number" ? data.column_count : undefined;
    // title is raw NDJSON; keep any extra details in the visible text.
    const parts = [
      sheet ? sheet : null,
      typeof tableIdx === "number" ? `Table ${tableIdx}` : "Table",
      "detected",
      typeof rows === "number" ? `rows=${rows}` : null,
      typeof cols === "number" ? `cols=${cols}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.table.extracted") {
    const sheet = asString(data.sheet_name);
    const tableIdx = typeof data.table_index === "number" ? data.table_index + 1 : undefined;
    const rows = typeof data.row_count === "number" ? data.row_count : undefined;
    const cols = typeof data.col_count === "number" ? data.col_count : undefined;
    const parts = [
      sheet ? sheet : null,
      typeof tableIdx === "number" ? `Table ${tableIdx}` : "Table",
      "extracted",
      typeof rows === "number" ? `rows=${rows}` : null,
      typeof cols === "number" ? `cols=${cols}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.table.mapped") {
    const sheet = asString(data.sheet_name);
    const tableIdx = typeof data.table_index === "number" ? data.table_index + 1 : undefined;
    const detectedFields = typeof data.detected_fields === "number" ? data.detected_fields : undefined;
    const expectedFields = typeof data.expected_fields === "number" ? data.expected_fields : undefined;
    const notDetectedFields = typeof data.not_detected_fields === "number" ? data.not_detected_fields : undefined;
    const parts = [
      sheet ? sheet : null,
      typeof tableIdx === "number" ? `Table ${tableIdx}` : "Table",
      "mapped",
      typeof detectedFields === "number" && typeof expectedFields === "number"
        ? `detected=${detectedFields}/${expectedFields}`
        : null,
      typeof notDetectedFields === "number" ? `not_detected=${notDetectedFields}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.table.mapping_patched") {
    const sheet = asString(data.sheet_name);
    const tableIdx = typeof data.table_index === "number" ? data.table_index + 1 : undefined;
    const parts = [sheet ? sheet : null, typeof tableIdx === "number" ? `Table ${tableIdx}` : "Table", "mapping patched"].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.table.normalized") {
    const sheet = asString(data.sheet_name);
    const tableIdx = typeof data.table_index === "number" ? data.table_index + 1 : undefined;
    const rows = typeof data.row_count === "number" ? data.row_count : undefined;
    const issues = typeof data.issue_count === "number" ? data.issue_count : undefined;
    const bySeverity = asRecord(data.issues_by_severity);
    const severitySummary = bySeverity ? formatTopCounts(bySeverity, 2) : null;
    const parts = [
      sheet ? sheet : null,
      typeof tableIdx === "number" ? `Table ${tableIdx}` : "Table",
      "normalized",
      typeof rows === "number" ? `rows=${rows}` : null,
      typeof issues === "number" ? `issues=${issues}` : null,
      severitySummary ? severitySummary : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.table.written") {
    const sheet = asString(data.sheet_name);
    const tableIdx = typeof data.table_index === "number" ? data.table_index : undefined;
    const range = asString(data.output_range);
    const counts = parseRenderedCounts(message);

    const label = [
      sheet ? sheet : null,
      typeof tableIdx === "number" ? `Table ${tableIdx + 1}` : null,
      "written",
      range ? range : null,
      counts ? `mapped=${counts.mapped} unmapped=${counts.unmapped}` : null,
    ]
      .filter(Boolean)
      .join(" · ");

    return <span className="break-words">{label || "Table written"}</span>;
  }

  if (name === "engine.validation.result") {
    const validator = typeof data.validator === "string" ? data.validator : undefined;
    const field = typeof data.field === "string" ? data.field : undefined;
    const issues = typeof data.issues_found === "number" ? data.issues_found : undefined;
    const col = typeof data.column_index === "number" ? data.column_index : undefined;
    const issuesSample = Array.isArray(data.results_sample) ? data.results_sample : [];
    const sample =
      typeof issues === "number" && issues > 0 && issuesSample.length > 0
        ? `sample=${truncate(JSON.stringify(issuesSample[0]), 80)}`
        : null;

    const parts = [
      "Validate",
      field ?? null,
      typeof col === "number" ? `Col ${indexToColumnLabel(col)}` : null,
      validator ? `via ${validator}` : null,
      typeof issues === "number" ? `issues=${issues}` : null,
      sample,
    ].filter(Boolean);
    return (
      <span className="break-words">
        {parts.join(" · ")}
      </span>
    );
  }

  if (name === "engine.validation.summary") {
    const total = typeof data.issues_total === "number" ? data.issues_total : undefined;
    return <span className="break-words">{`Validation summary${typeof total === "number" ? ` · issues=${total}` : ""}`}</span>;
  }

  if (name === "engine.transform.result") {
    const transform = typeof data.transform === "string" ? data.transform : undefined;
    const field = typeof data.field === "string" ? data.field : undefined;
    const inLen = typeof data.input_len === "number" ? data.input_len : undefined;
    const outLen = typeof data.output_len === "number" ? data.output_len : undefined;
    const rowCount = typeof data.row_count === "number" ? data.row_count : undefined;
    const parts = [
      transform ? `Transform ${transform}` : "Transform",
      field ?? null,
      typeof rowCount === "number" ? `rows=${rowCount}` : null,
      typeof inLen === "number" && typeof outLen === "number" ? `${inLen}→${outLen}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.transform.derived_merge") {
    const field = asString(data.field);
    const mode = asString(data.mode);
    const parts = ["Derived merge", field ?? null, mode ? `mode=${mode}` : null].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.column_detector.candidate") {
    const col = typeof data.column_index === "number" ? data.column_index : undefined;
    const header = typeof data.header === "string" ? data.header : undefined;
    const best = typeof data.best_field === "string" ? data.best_field : undefined;
    const score = typeof data.best_score === "number" ? data.best_score : undefined;
    const scores = asRecord(data.scores);
    const topScores = scores ? formatTopScores(scores, 3) : null;
    const contributions = asRecord(data.contributions);
    const topSignals = contributions ? formatTopScores(contributions, 2) : null;
    const parts = [
      typeof col === "number" ? `Col ${indexToColumnLabel(col)}` : null,
      header ? `"${truncate(header, 32)}"` : null,
      best ? `suggested=${best}` : null,
      typeof score === "number" ? `(${score.toFixed(3)})` : null,
      topScores ? `why: ${topScores}` : null,
      topSignals ? `signals: ${topSignals}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.column_detector.summary") {
    const mapped = Array.isArray(data.mapped) ? data.mapped : [];
    const total = typeof data.total_columns === "number" ? data.total_columns : undefined;
    const unmapped = Array.isArray(data.unmapped_indices) ? data.unmapped_indices.length : undefined;
    const parts = [
      "Columns",
      typeof total === "number" ? `total=${total}` : null,
      `mapped=${mapped.length}`,
      typeof unmapped === "number" ? `unmapped=${unmapped}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.row_detector.summary") {
    const sheet = asString(data.sheet_name);
    const headerRow = typeof data.header_row_index === "number" ? data.header_row_index + 1 : undefined;
    const headerScore = typeof data.header_score === "number" ? data.header_score : undefined;
    const dataStart = typeof data.data_start_index === "number" ? data.data_start_index + 1 : undefined;
    const dataEnd = typeof data.data_end_index === "number" ? data.data_end_index + 1 : undefined;
    const parts = [
      sheet ? `${sheet}` : "Rows",
      typeof headerRow === "number" ? `headerRow=${headerRow}` : null,
      typeof headerScore === "number" ? `score=${headerScore.toFixed(3)}` : null,
      typeof dataStart === "number" && typeof dataEnd === "number" ? `dataRows=${dataStart}..${dataEnd}` : null,
    ].filter(Boolean);
    return <span className="break-words">{parts.join(" · ")}</span>;
  }

  if (name === "engine.detector.column_result" || name === "engine.detector.row_result") {
    const sheet = typeof data.sheet_name === "string" ? data.sheet_name : undefined;
    const col = typeof data.column_index === "number" ? data.column_index : undefined;
    const row = typeof data.row_index === "number" ? data.row_index : undefined;
    const detector = data.detector && typeof data.detector === "object" ? (data.detector as Record<string, unknown>) : {};
    const detName = typeof detector.name === "string" ? detector.name : undefined;
    const duration = typeof detector.duration_ms === "number" ? detector.duration_ms : undefined;
    const scores = detector.scores && typeof detector.scores === "object" ? (detector.scores as Record<string, unknown>) : null;
    const scoreSummary = scores ? formatTopScores(scores as Record<string, unknown>, 2) : null;
    return (
      <span className="break-words">
        {[
          sheet ? sheet : null,
          typeof col === "number" ? `Col ${indexToColumnLabel(col)}` : null,
          typeof row === "number" ? `Row ${row + 1}` : null,
          detName ? `ran ${detName}` : "ran detector",
          typeof duration === "number" ? formatDurationMs(duration) : null,
          scoreSummary ? `scores: ${scoreSummary}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </span>
    );
  }

  if (name === "engine.row_classification") {
    const sheet = asString(data.sheet_name);
    const row = typeof data.row_index === "number" ? data.row_index + 1 : undefined;
    const scores = asRecord(data.scores);
    const topScores = scores ? formatTopScores(scores, 2) : null;
    const classification = asRecord(data.classification);
    const kind = asString(classification?.row_kind);
    const score = typeof classification?.score === "number" ? classification.score : undefined;
    const considered = Array.isArray(classification?.considered_row_kinds) ? classification?.considered_row_kinds.length : undefined;
    return (
      <span className="break-words">
        {[
          sheet ? sheet : null,
          typeof row === "number" ? `Row ${row}` : "Row",
          kind ? `label=${kind}` : null,
          typeof score === "number" ? `(${score.toFixed(3)})` : null,
          typeof considered === "number" ? `considered=${considered}` : null,
          topScores ? `why: ${topScores}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </span>
    );
  }

  if (name === "engine.column_classification") {
    const sheet = asString(data.sheet_name);
    const col = typeof data.column_index === "number" ? data.column_index : undefined;
    const scores = asRecord(data.scores);
    const topScores = scores ? formatTopScores(scores, 2) : null;
    const classification = asRecord(data.classification);
    const field = asString(classification?.field);
    const score = typeof classification?.score === "number" ? classification.score : undefined;
    const considered = Array.isArray(classification?.considered_fields) ? classification?.considered_fields.length : undefined;
    return (
      <span className="break-words">
        {[
          sheet ? sheet : null,
          typeof col === "number" ? `Col ${indexToColumnLabel(col)}` : "Col",
          field ? `label=${field}` : null,
          typeof score === "number" ? `(${score.toFixed(3)})` : null,
          typeof considered === "number" ? `considered=${considered}` : null,
          topScores ? `why: ${topScores}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </span>
    );
  }

  if (message && message !== name) {
    return <span className="break-words">{message}</span>;
  }

  if (Object.keys(data).length) {
    // For debug-heavy unknown events, show a compact one-liner.
    if (level === "debug" && name.startsWith("engine.")) {
      return <span className="break-words">{name}</span>;
    }
    return <span className="break-words">{name}</span>;
  }

  return null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

function basename(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const parts = trimmed.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] ?? trimmed;
}

function truncate(value: string, max: number): string {
  if (value.length <= max) return value;
  return value.slice(0, Math.max(0, max - 1)) + "…";
}

function indexToColumnLabel(index: number): string {
  // 0 -> A, 25 -> Z, 26 -> AA ...
  let n = Math.floor(index);
  if (!Number.isFinite(n) || n < 0) return String(index);
  let out = "";
  while (n >= 0) {
    out = String.fromCharCode((n % 26) + 65) + out;
    n = Math.floor(n / 26) - 1;
  }
  return out;
}

function formatDurationMs(valueMs: number): string {
  if (!Number.isFinite(valueMs) || valueMs < 0) return `${valueMs}ms`;
  if (valueMs < 1) return `${valueMs.toFixed(3)}ms`;
  if (valueMs < 10) return `${valueMs.toFixed(2)}ms`;
  if (valueMs < 100) return `${valueMs.toFixed(1)}ms`;
  if (valueMs < 1000) return `${Math.round(valueMs)}ms`;
  return `${(valueMs / 1000).toFixed(2)}s`;
}

function formatTopScores(scores: Record<string, unknown>, limit: number): string | null {
  const pairs: Array<[string, number]> = [];
  for (const [key, value] of Object.entries(scores)) {
    if (typeof value === "number" && Number.isFinite(value)) {
      pairs.push([key, value]);
    }
  }
  if (!pairs.length) return null;
  pairs.sort((a, b) => b[1] - a[1]);
  return pairs
    .slice(0, Math.max(1, limit))
    .map(([k, v]) => `${k}=${v.toFixed(3)}`)
    .join(" ");
}

function formatTopCounts(counts: Record<string, unknown>, limit: number): string | null {
  const pairs: Array<[string, number]> = [];
  for (const [key, value] of Object.entries(counts)) {
    if (typeof value === "number" && Number.isFinite(value)) {
      pairs.push([key, value]);
    }
  }
  if (!pairs.length) return null;
  pairs.sort((a, b) => b[1] - a[1]);
  return pairs
    .slice(0, Math.max(1, limit))
    .map(([k, v]) => `${k}=${Math.round(v)}`)
    .join(" ");
}

function parseRenderedCounts(message: string): { mapped: number; unmapped: number } | null {
  const m = message.match(/Rendered table with\s+(\d+)\s+\w+\s+columns?\s+and\s+(\d+)\s+unmapped/i);
  if (!m) return null;
  const mapped = Number(m[1]);
  const unmapped = Number(m[2]);
  if (!Number.isFinite(mapped) || !Number.isFinite(unmapped)) return null;
  return { mapped, unmapped };
}

function parseConfigHook(message: string): { text: string; title?: string } {
  const raw = (message || "").trim();
  if (!raw) return { text: "" };

  // Common patterns:
  // - "Config hook: workbook start (<path>)"
  // - "Config hook: sheet start (NOV 2025)"
  // - "Config hook: table detected (sheet=..., header_row=..., mapped_columns=...)"
  // - "Config hook: table mapped (detected_fields=[...])"
  // - "Config hook: table written (rows=..., issues=...)"
  // - "Config hook: workbook before save (<path>)"
  const prefix = "Config hook:";
  const text = raw.startsWith(prefix) ? raw.slice(prefix.length).trim() : raw;

  const workbookStart = text.match(/^workbook start\s*\((.+)\)\s*$/i);
  if (workbookStart) {
    const path = workbookStart[1];
    const file = basename(path);
    return { text: `Workbook start · ${file}`, title: path };
  }

  const workbookBeforeSave = text.match(/^workbook before save\s*\((.+)\)\s*$/i);
  if (workbookBeforeSave) {
    const path = workbookBeforeSave[1];
    const file = basename(path);
    return { text: `Workbook save · ${file}`, title: path };
  }

  const sheetStart = text.match(/^sheet start\s*\((.+)\)\s*$/i);
  if (sheetStart) {
    return { text: `Sheet start · ${sheetStart[1]}` };
  }

  const tableDetected = text.match(/^table detected\s*\((.+)\)\s*$/i);
  if (tableDetected) {
    // keep the inside, but normalize key/value separators a bit
    return { text: `Table detected · ${tableDetected[1].replace(/\s*,\s*/g, " · ")}` };
  }

  const tableMapped = text.match(/^table mapped\s*\((.+)\)\s*$/i);
  if (tableMapped) {
    const inside = tableMapped[1];
    const detectedFields = inside.match(/detected_fields=\[(.*)\]/i);
    if (detectedFields) {
      const count = detectedFields[1].split(",").map((s) => s.trim()).filter(Boolean).length;
      return { text: `Table mapped · detected=${count}`, title: inside };
    }
    return { text: `Table mapped · ${inside}` };
  }

  const tableWritten = text.match(/^table written\s*\((.+)\)\s*$/i);
  if (tableWritten) {
    return { text: `Table written · ${tableWritten[1].replace(/\s*,\s*/g, " · ")}` };
  }

  // Fall back to the original message without adding the event name.
  return { text: raw };
}

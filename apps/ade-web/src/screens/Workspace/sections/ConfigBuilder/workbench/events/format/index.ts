import { eventTimestamp, isAdeEvent } from "@shared/runs/types";
import type { AdeEvent as RunStreamEvent } from "@shared/runs/types";

import type { WorkbenchConsoleLine } from "../../types";
import {
  formatConsole,
  formatConsoleTimestamp,
  formatDurationMs,
  isBuildEvent,
  isConsoleLine,
  normalizeLevel,
  payloadOf,
  timestampLabel,
} from "./common";

type EventFormatter = (event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string) => WorkbenchConsoleLine;
type PrefixFormatter = (type: string, payload: Record<string, unknown>, timestamp: string) => WorkbenchConsoleLine;
type PrefixHandler = { prefix: string; formatter: PrefixFormatter };

const BUILD_EVENT_HANDLERS: Record<string, EventFormatter> = {
  "build.queued": (_event, payload, timestamp) => formatBuildQueued(payload, timestamp),
  "build.created": (_event, payload, timestamp) => formatBuildCreated(payload, timestamp),
  "build.started": (_event, payload, timestamp) => formatBuildStarted(payload, timestamp),
  "build.start": (_event, payload, timestamp) => formatBuildStarted(payload, timestamp),
  "build.phase.started": (_event, payload, timestamp) => formatBuildPhaseStarted(payload, timestamp),
  "build.phase.start": (_event, payload, timestamp) => formatBuildPhaseStarted(payload, timestamp),
  "build.progress": (_event, payload, timestamp) => formatBuildProgress(payload, timestamp),
  "build.phase.completed": (_event, payload, timestamp) => formatBuildPhaseCompleted(payload, timestamp),
  "build.phase.complete": (_event, payload, timestamp) => formatBuildPhaseCompleted(payload, timestamp),
  "build.completed": (_event, payload, timestamp) => formatBuildCompletion(payload, timestamp),
  "build.complete": (_event, payload, timestamp) => formatBuildCompletion(payload, timestamp),
};

const RUN_EVENT_HANDLERS: Record<string, EventFormatter> = {
  "run.queued": (event, payload, timestamp) => formatRunQueued(event, payload, timestamp),
  "run.waiting_for_build": (_event, payload, timestamp) => formatRunWaitingForBuild(payload, timestamp),
  "run.started": (_event, payload, timestamp) => formatRunStarted(payload, timestamp),
  "run.start": (_event, payload, timestamp) => formatRunStarted(payload, timestamp),
  "engine.start": (_event, payload, timestamp) => formatRunStarted(payload, timestamp),
  "run.phase.started": (_event, payload, timestamp) => formatRunPhaseStarted(payload, timestamp),
  "run.phase.start": (_event, payload, timestamp) => formatRunPhaseStarted(payload, timestamp),
  "engine.phase.start": (_event, payload, timestamp) => formatRunPhaseStarted(payload, timestamp),
  "run.phase.completed": (_event, payload, timestamp) => formatRunPhaseCompleted(payload, timestamp),
  "run.phase.complete": (_event, payload, timestamp) => formatRunPhaseCompleted(payload, timestamp),
  "engine.phase.complete": (_event, payload, timestamp) => formatRunPhaseCompleted(payload, timestamp),
  "run.table.summary": (_event, payload, timestamp) => formatRunTableSummary(payload, timestamp),
  "engine.table.summary": (_event, payload, timestamp) => formatRunTableSummary(payload, timestamp),
  "run.column_detector.score": (_event, payload, timestamp) => formatColumnDetectorScore(payload, timestamp),
  "engine.detector.column.score": (_event, payload, timestamp) => formatColumnDetectorScore(payload, timestamp),
  "run.row_detector.score": (_event, payload, timestamp) => formatRowDetectorScore(payload, timestamp),
  "engine.detector.row.score": (_event, payload, timestamp) => formatRowDetectorScore(payload, timestamp),
  "run.hook.checkpoint": (_event, payload, timestamp) => formatHookCheckpoint(payload, timestamp),
  "run.hook.mapping_checked": (_event, payload, timestamp) => formatMappingChecked(payload, timestamp),
  "engine.file.summary": (_event, payload, timestamp) => formatFileSummary(payload, timestamp),
  "engine.sheet.summary": (_event, payload, timestamp) => formatSheetSummary(payload, timestamp),
  "run.validation.issue": (_event, payload, timestamp) => formatValidationIssue(payload, timestamp),
  "engine.validation.issue": (_event, payload, timestamp) => formatValidationIssue(payload, timestamp),
  "run.validation.summary": (_event, payload, timestamp) => formatValidationSummary(payload, timestamp),
  "engine.validation.summary": (_event, payload, timestamp) => formatValidationSummary(payload, timestamp),
  "run.error": (_event, payload, timestamp) => formatRunError(payload, timestamp),
  "run.complete": (event, payload, timestamp) => formatRunCompletionOrSummary(event, payload, timestamp),
  "engine.complete": (event, payload, timestamp) => formatRunCompletionOrSummary(event, payload, timestamp),
  "engine.run.summary": (event, payload, timestamp) => formatRunCompletionOrSummary(event, payload, timestamp),
};

const RUN_PREFIX_HANDLERS: PrefixHandler[] = [
  { prefix: "config.", formatter: (type, payload, timestamp) => formatConfigEvent(type, payload, timestamp) },
  { prefix: "run.transform.", formatter: (type, payload, timestamp) => formatTransformEvent(type, payload, timestamp) },
];

export function formatConsoleEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  return isBuildEvent(event) ? formatBuildEvent(event) : formatRunEvent(event);
}

export { formatConsoleTimestamp } from "./common";

// --------------------------------------------------------------------------- //
// Build events
// --------------------------------------------------------------------------- //

export function formatBuildEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isAdeEvent(event)) {
    return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" });
  }
  const payload = payloadOf(event);
  const ts = timestampLabel(event);
  const type = event.type;

  if (type === "console.line") {
    return withRaw(event, formatConsole(event, payload, ts, "build"));
  }

  if (!type?.startsWith("build.")) {
    return withRaw(event, {
      level: "info",
      message: JSON.stringify(event),
      timestamp: ts,
      origin: "build",
    });
  }

  const handler = type ? BUILD_EVENT_HANDLERS[type] : null;
  if (handler) {
    return withRaw(event, handler(event, payload, ts));
  }

  return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: ts, origin: "build" });
}

function formatBuildCompletion(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const status = (payload.status as string | undefined) ?? "completed";
  const summary = (payload.summary as string | undefined)?.trim();
  const exitCode = typeof payload.exit_code === "number" ? payload.exit_code : undefined;
  const errorMessage =
    typeof payload.error === "object" && payload.error !== null
      ? ((payload.error as Record<string, unknown>).message as string | undefined)
      : undefined;

  if (status === "succeeded" || status === "reused") {
    return {
      level: "success",
      message: summary || `Build ${status}.`,
      timestamp,
      origin: "build",
      raw: payload,
    };
  }
  if (status === "cancelled") {
    return { level: "warning", message: "Build was cancelled before completion.", timestamp, origin: "build", raw: payload };
  }
  if (status === "failed") {
    const exit = typeof exitCode === "number" ? ` (exit code ${exitCode})` : "";
    return {
      level: "error",
      message: (errorMessage || summary || "Build failed.") + exit,
      timestamp,
      origin: "build",
      raw: payload,
    };
  }
  if (status === "skipped") {
    return {
      level: "info",
      message: summary || "Build skipped.",
      timestamp,
      origin: "build",
      raw: payload,
    };
  }
  return {
    level: "info",
    message: summary || `Build ${status}.`,
    timestamp,
    origin: "build",
    raw: payload,
  };
}

function formatBuildQueued(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? undefined;
  return {
    level: "info",
    message: reason ? `Build queued (${reason}).` : "Build queued.",
    timestamp,
    origin: "build",
  };
}

function formatBuildCreated(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? "queued";
  return {
    level: "info",
    message: `Build queued (${reason}).`,
    timestamp,
    origin: "build",
  };
}

function formatBuildStarted(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? undefined;
  return {
    level: "info",
    message: reason ? `Build started (${reason}).` : "Build started.",
    timestamp,
    origin: "build",
  };
}

function formatBuildPhaseStarted(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "building";
  const message = (payload.message as string | undefined) ?? `Starting ${phase}`;
  return { level: "info", message, timestamp, origin: "build" };
}

function formatBuildProgress(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const message =
    (payload.message as string | undefined) ??
    ((payload.step as string | undefined) ? `Build: ${payload.step as string}` : "Build progress");
  return { level: "info", message, timestamp, origin: "build" };
}

function formatBuildPhaseCompleted(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "build";
  const status = (payload.status as string | undefined) ?? "completed";
  const duration = formatDurationMs(payload.duration_ms);
  const message =
    (payload.message as string | undefined) ??
    `${phase} ${status}${duration ? ` in ${duration}` : ""}`;
  const level: WorkbenchConsoleLine["level"] =
    status === "failed" ? "error" : status === "skipped" ? "warning" : "success";
  return { level, message, timestamp, origin: "build" };
}

// --------------------------------------------------------------------------- //
// Run/config/engine events
// --------------------------------------------------------------------------- //

export function formatRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isAdeEvent(event)) {
    return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" });
  }
  const payload = payloadOf(event);
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const type = event.type;

  if (isConsoleLine(event)) {
    return withRaw(
      event,
      formatConsole(event, payload, ts, (payload.scope as string | undefined) === "build" ? "build" : "run"),
    );
  }

  if (!type?.startsWith("run.") && !type?.startsWith("engine.") && !type?.startsWith("config.")) {
    return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: ts, origin: "run" });
  }

  const handler = type ? RUN_EVENT_HANDLERS[type] : null;
  if (handler) {
    return withRaw(event, handler(event, payload, ts));
  }

  const prefix = type ? RUN_PREFIX_HANDLERS.find((entry) => type.startsWith(entry.prefix)) : undefined;
  if (prefix) {
    return withRaw(event, prefix.formatter(type, payload, ts));
  }

  return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: ts, origin: "run" });
}

function formatRunQueued(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const mode = (payload.mode as string | undefined) ?? undefined;
  const runId = event.run_id ?? "";
  const suffix = mode ? ` (${mode})` : "";
  return {
    level: "info",
    message: `Run ${runId ? `${runId} ` : ""}queued${suffix}.`,
    timestamp,
    origin: "run",
  };
}

function formatRunWaitingForBuild(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? undefined;
  const buildId = (payload.build_id as string | undefined) ?? undefined;
  const reasonPart = reason ? ` (${reason})` : "";
  const buildPart = buildId ? ` · ${buildId}` : "";
  return {
    level: "info",
    message: `Waiting for build${reasonPart}${buildPart}.`,
    timestamp,
    origin: "run",
  };
}

function formatRunStarted(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const mode = (payload.mode as string | undefined) ?? undefined;
  const env = (payload.env as { reused?: boolean; reason?: string } | undefined) ?? undefined;
  const envNote = env?.reused ? " (reused environment)" : env?.reason ? ` (${env.reason})` : "";
  return {
    level: "info",
    message: `Run started${mode ? ` (${mode})` : ""}${envNote}.`,
    timestamp,
    origin: "run",
  };
}

function formatRunPhaseStarted(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "progress";
  const message = (payload.message as string | undefined) ?? `Phase: ${phase}`;
  const level = normalizeLevel((payload.level as string | undefined) ?? "info");
  return {
    level,
    message,
    timestamp,
    origin: "run",
  };
}

function formatRunPhaseCompleted(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "phase";
  const status = (payload.status as string | undefined) ?? "completed";
  const duration = formatDurationMs(payload.duration_ms);
  const message =
    (payload.message as string | undefined) ??
    `Phase ${phase} ${status}${duration ? ` in ${duration}` : ""}`;
  const level: WorkbenchConsoleLine["level"] =
    status === "failed" ? "error" : status === "skipped" ? "warning" : "success";
  return {
    level,
    message,
    timestamp,
    origin: "run",
  };
}

function formatRunTableSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  if (isAdeSummary(payload, "table")) {
    return formatTableSummary(payload, timestamp);
  }
  return formatLegacyTableSummary(payload, timestamp);
}

function formatValidationIssue(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const sev = (payload.severity as string | undefined) ?? "info";
  return {
    level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
    message: `Validation issue${payload.code ? `: ${payload.code as string}` : ""}`,
    timestamp,
    origin: "run",
  };
}

function formatValidationSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const total = (payload.issues_total as number | undefined) ?? 0;
  const maxSeverity = (payload.max_severity as string | undefined) ?? undefined;
  const level: WorkbenchConsoleLine["level"] =
    maxSeverity === "error" ? "error" : maxSeverity === "warning" || total > 0 ? "warning" : "info";
  const descriptor = maxSeverity ? `${maxSeverity}` : total > 0 ? "issues" : "clean";
  return {
    level,
    message: `Validation summary: ${total} ${descriptor}`,
    timestamp,
    origin: "run",
  };
}

function formatRunError(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const code = (payload.code as string | undefined) ?? "unknown_error";
  const message = (payload.message as string | undefined) ?? "Run error.";
  const stage = (payload.stage as string | undefined) ?? (payload.phase as string | undefined);
  const stageLabel = stage ? ` [${stage}]` : "";
  return {
    level: "error",
    message: `${message}${stageLabel} (${code})`,
    timestamp,
    origin: "run",
  };
}

function formatRunCompletionOrSummary(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  if (isAdeSummary(payload, "run")) {
    return formatRunSummary(payload, timestamp);
  }
  return formatRunCompletion(event, payload, timestamp);
}

function formatRunCompletion(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const isRunSummary = payload.scope === "run" && typeof payload.source === "object";
  const source = (payload.source as Record<string, unknown> | undefined) ?? {};
  const status = isRunSummary
    ? ((source.status as string | undefined) ?? "completed")
    : (payload.status as string | undefined) ?? "completed";
  const execution = isRunSummary ? {} : (payload.execution as Record<string, unknown> | undefined) ?? {};
  const exit = typeof execution.exit_code === "number" ? execution.exit_code : undefined;
  const failure = (isRunSummary ? source.failure : payload.failure) as Record<string, unknown> | undefined;
  const failureMessage = typeof failure?.message === "string" ? failure.message.trim() : null;
  const summaryMessage =
    typeof payload.summary === "string"
      ? payload.summary.trim()
      : null;
  const artifacts = (!isRunSummary &&
    payload.artifacts &&
    typeof payload.artifacts === "object" &&
    (payload.artifacts as Record<string, unknown>)) || null;
  const outputPath =
    artifacts && typeof (artifacts as { output_path?: unknown }).output_path === "string"
      ? ((artifacts as { output_path: string }).output_path as string)
      : null;
  const eventsPath = artifacts && typeof artifacts.events_path === "string" ? artifacts.events_path : null;
  const durationText = !isRunSummary ? formatDurationMs(execution.duration_ms) : null;
  const cancelled = status === "cancelled";
  const level: WorkbenchConsoleLine["level"] =
    status === "failed"
      ? "error"
      : cancelled
        ? "warning"
        : status === "succeeded"
          ? "success"
          : "info";

  const base = failureMessage || summaryMessage || `Run ${status}`;
  const exitPart = typeof exit === "number" ? ` (exit code ${exit})` : "";
  const headline = `${base}${exitPart}${durationText ? ` in ${durationText}` : ""}.`;
  const runId = event.run_id ?? null;
  const parsedOutput = outputPath
    ? {
        path: outputPath,
        label: basename(outputPath),
        href: buildRunOutputUrl(runId),
      }
    : null;
  const structured = {
    type: "ade.console.run_complete",
    headline,
    output: parsedOutput,
    eventsPath,
  };
  return {
    level,
    message: JSON.stringify(structured),
    timestamp,
    origin: "run",
  };
}

function withRaw(event: RunStreamEvent, line: WorkbenchConsoleLine): WorkbenchConsoleLine {
  return { ...line, raw: event };
}

function formatConfigEvent(type: string, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const message =
    typeof payload.message === "string" ? payload.message : `Config event: ${type.replace(/^config\\./, "")}`;
  return {
    level: normalizeLevel((payload.level as string | undefined) ?? "info"),
    message,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatTransformEvent(
  type: string,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const phase = type.replace("run.transform.", "");
  const level = normalizeLevel((payload.level as string | undefined) ?? "info");
  const message =
    (payload.message as string | undefined) ??
    `Transform ${phase}${payload.status ? ` ${payload.status as string}` : ""}`;
  return {
    level,
    message,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function isAdeSummary(payload: Record<string, unknown>, expectedScope: string): boolean {
  const scope = payload.scope === expectedScope;
  const schema = typeof payload.schema_id === "string" && payload.schema_id.startsWith("ade.summary");
  const isSummary = payload.type === "summary" || scope || schema;
  return isSummary;
}

function formatTableSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const source = (payload.source as Record<string, unknown> | undefined) ?? {};
  const sheet = (source.sheet_name as string | undefined) ?? "sheet";
  const tableIndex = asNumber(source.table_index) ?? 0;
  const outputSheet = (source.output_sheet as string | undefined) ?? undefined;
  const counts = (payload.counts as Record<string, unknown> | undefined) ?? {};
  const rows = asNumber((counts.rows as Record<string, unknown> | undefined)?.total);
  const cols = asNumber((counts.columns as Record<string, unknown> | undefined)?.physical_total);
  const fields = (counts.fields as Record<string, unknown> | undefined) ?? {};
  const required = asNumber(fields.required);
  const requiredUnmapped = asNumber(fields.required_unmapped) ?? 0;
  const mappedFields = asNumber(fields.mapped);
  const totalFields = asNumber(fields.total);
  const headerCounts = (counts.columns as Record<string, unknown> | undefined) ?? {};
  const mappedHeaders = asNumber(headerCounts.distinct_headers_mapped);
  const totalHeaders = asNumber(headerCounts.distinct_headers);

  const fieldsList = Array.isArray(payload.fields) ? (payload.fields as Array<Record<string, unknown>>) : [];
  const unmappedRequiredFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.required === true && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const detailParts = formatTableDetails(payload.details, source.file_path as string | undefined);
  const headlineParts = [
    `Table summary: ${sheet}${outputSheet ? ` → ${outputSheet}` : ""}`,
    `table ${tableIndex}`,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
  ].filter(Boolean);

  const mappedLine =
    totalFields !== undefined && mappedFields !== undefined
      ? `mapped fields ${mappedFields}/${totalFields}${required !== undefined ? ` · required missing ${requiredUnmapped}/${required}` : ""}`
      : required !== undefined
        ? `required missing ${requiredUnmapped}/${required}`
        : null;

  const headerLine =
    mappedHeaders !== undefined && totalHeaders !== undefined
      ? `headers mapped ${mappedHeaders}/${totalHeaders}`
      : null;

  const details: string[] = [];
  if (unmappedRequiredFields.length) {
    details.push(`Unmapped fields: ${unmappedRequiredFields.join(", ")}`);
  }
  const messageLines = [
    headlineParts.join(" · "),
    mappedLine,
    headerLine,
    detailParts ? `(${detailParts})` : null,
  ]
    .concat(details)
    .filter(Boolean);

  const level: WorkbenchConsoleLine["level"] =
    requiredUnmapped > 0 ? "error" : mappedHeaders !== undefined && totalHeaders !== undefined && mappedHeaders < totalHeaders
      ? "warning"
      : "success";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatLegacyTableSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const name =
    (payload.source_sheet as string | undefined) ??
    (payload.source_file as string | undefined) ??
    (payload.table_id as string | undefined) ??
    "table";
  const mappedColumns = asNumber(payload.mapped_column_count);
  const columnCount = asNumber(payload.column_count);
  const rowCount = asNumber(payload.row_count);
  const coveragePct =
    columnCount && mappedColumns !== undefined && columnCount > 0
      ? (mappedColumns / columnCount) * 100
      : null;
  const mappedSummary =
    columnCount && mappedColumns !== undefined
      ? `mapped ${mappedColumns}/${columnCount} (${formatPercent(coveragePct)})`
      : mappedColumns !== undefined
        ? `mapped ${mappedColumns} column${mappedColumns === 1 ? "" : "s"}`
        : null;

  const missingRequired = collectMissingRequired(payload);
  const unmappedHeaders = collectUnmappedHeaders(payload);

  const line1Parts = [
    `Table ${name}:`,
    rowCount !== undefined ? `${rowCount} row${rowCount === 1 ? "" : "s"}` : null,
    columnCount !== undefined ? `${columnCount} col${columnCount === 1 ? "" : "s"}` : null,
    mappedSummary,
  ].filter(Boolean);

  const line2Parts = [
    missingRequired.length ? `Missing required: ${formatList(missingRequired, 3)}` : null,
    unmappedHeaders.length ? `Unmapped: ${formatList(unmappedHeaders, 100)}` : null,
  ].filter(Boolean);

  const detailParts = formatTableDetails(payload.details, payload.source_file as string | undefined);
  const messageLines = [
    line1Parts.join(" · "),
    line2Parts.find((line) => line?.startsWith("Missing required")) ?? null,
    line2Parts.find((line) => line?.startsWith("Unmapped")) ?? null,
    detailParts ? `(${detailParts})` : null,
  ].filter(Boolean);

  const level: WorkbenchConsoleLine["level"] =
    missingRequired.length > 0 ? "warning" : coveragePct !== null && coveragePct >= 85 ? "success" : "info";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatFileSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const sourcePath = typeof payload.source === "object" && payload.source
    ? (payload.source as Record<string, unknown>).file_path as string | undefined
    : undefined;
  const fileName = sourcePath ? basename(sourcePath) : "file";
  const counts = (payload.counts as Record<string, unknown> | undefined) ?? {};
  const rows = asNumber((counts.rows as Record<string, unknown> | undefined)?.total);
  const cols = asNumber((counts.columns as Record<string, unknown> | undefined)?.physical_total);
  const tables = asNumber((counts.tables as Record<string, unknown> | undefined)?.total);
  const sheets = asNumber((counts.sheets as Record<string, unknown> | undefined)?.total);
  const fields = (counts.fields as Record<string, unknown> | undefined) ?? {};
  const required = asNumber(fields.required);
  const requiredUnmapped = asNumber(fields.required_unmapped) ?? 0;
  const mappedFields = asNumber(fields.mapped);
  const totalFields = asNumber(fields.total);

  const headerCounts = (counts.columns as Record<string, unknown> | undefined) ?? {};
  const mappedHeaders = asNumber(headerCounts.distinct_headers_mapped);
  const totalHeaders = asNumber(headerCounts.distinct_headers);

  const fieldsList = Array.isArray(payload.fields) ? (payload.fields as Array<Record<string, unknown>>) : [];
  const unmappedRequiredFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.required === true && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const detailParts = formatTableDetails(payload.details, sourcePath);
  const headlineParts = [
    `File summary: ${fileName}`,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
    tables !== undefined ? `tables ${tables}` : null,
    sheets !== undefined ? `sheets ${sheets}` : null,
  ].filter(Boolean);

  const mappedLine =
    totalFields !== undefined && mappedFields !== undefined
      ? `mapped fields ${mappedFields}/${totalFields}${required !== undefined ? ` · required missing ${requiredUnmapped}/${required}` : ""}`
      : required !== undefined
        ? `required missing ${requiredUnmapped}/${required}`
        : null;

  const headerLine =
    mappedHeaders !== undefined && totalHeaders !== undefined
      ? `headers mapped ${mappedHeaders}/${totalHeaders}`
      : null;

  const details: string[] = [];
  if (unmappedRequiredFields.length) {
    details.push(`Unmapped fields: ${unmappedRequiredFields.join(", ")}`);
  }
  const messageLines = [
    headlineParts.join(" · "),
    mappedLine,
    headerLine,
    detailParts ? `(${detailParts})` : null,
  ]
    .concat(details)
    .filter(Boolean);

  const level: WorkbenchConsoleLine["level"] =
    requiredUnmapped > 0
      ? "error"
      : mappedHeaders !== undefined && totalHeaders !== undefined && mappedHeaders < totalHeaders
        ? "warning"
        : "success";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatSheetSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const sourcePath = typeof payload.source === "object" && payload.source
    ? (payload.source as Record<string, unknown>).file_path as string | undefined
    : undefined;
  const sheet = typeof payload.sheet === "object" && payload.sheet
    ? (payload.sheet as Record<string, unknown>).name as string | undefined
    : undefined;
  const counts = (payload.counts as Record<string, unknown> | undefined) ?? {};
  const rows = asNumber((counts.rows as Record<string, unknown> | undefined)?.total);
  const cols = asNumber((counts.columns as Record<string, unknown> | undefined)?.physical_total);
  const tables = asNumber((counts.tables as Record<string, unknown> | undefined)?.total);

  const details = formatTableDetails(payload.details, sourcePath);
  const headlineParts = [
    `Sheet summary: ${sheet ?? "sheet"}`,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
    tables !== undefined ? `tables ${tables}` : null,
  ].filter(Boolean);

  const messageLines = [
    headlineParts.join(" · "),
    details ? `(${details})` : null,
  ].filter(Boolean);

  const level: WorkbenchConsoleLine["level"] = "info";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatColumnDetectorScore(
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const field = (payload.field as string | undefined) ?? "field";
  const threshold = asNumber(payload.threshold);
  const chosen = (payload.chosen as Record<string, unknown> | undefined) ?? {};
  const header = (chosen.header as string | undefined) ?? "unknown";
  const score = asNumber(chosen.score) ?? 0;
  const passed = chosen.passed_threshold === true;
  const columnIndex = asNumber(chosen.column_index) ?? asNumber(chosen.source_column_index);
  const candidates = Array.isArray(payload.candidates)
    ? (payload.candidates as Array<Record<string, unknown>>)
    : [];
  const candidatePreview = candidates
    .slice(0, 3)
    .map((candidate) => {
      const name = (candidate.header as string | undefined) ?? `col ${asNumber(candidate.column_index) ?? "?"}`;
      const candidateScore = formatScore(asNumber(candidate.score));
      const ok = candidate.passed_threshold === true ? "✓" : "";
      return `"${name}" ${candidateScore}${ok ? ` ${ok}` : ""}`;
    })
    .join(" | ");
  const contributions = Array.isArray(chosen.contributions)
    ? (chosen.contributions as Array<Record<string, unknown>>)
    : [];
  const contribPreview = contributions
    .slice(0, 3)
    .map((entry) => `${shortName(entry.detector as string)} ${formatScore(asNumber(entry.delta))}`)
    .join(", ");

  const passedText =
    threshold !== undefined
      ? `${formatScore(score)} ${passed ? "≥" : "<"} ${formatScore(threshold)}`
      : formatScore(score);
  const primary = passed
    ? `Matched ${field} to "${header}"${columnIndex !== undefined ? ` (col ${columnIndex})` : ""} · score ${passedText}`
    : `No match for ${field}${threshold !== undefined ? ` (score ${passedText})` : ""}`;
  const secondary = candidatePreview ? `Top candidates: ${candidatePreview}` : "";
  const tertiary = contribPreview ? `Signals: ${contribPreview}` : "";
  const level: WorkbenchConsoleLine["level"] = passed ? "success" : "warning";

  return {
    level,
    message: [primary, secondary, tertiary].filter(Boolean).join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatRowDetectorScore(
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const thresholds = (payload.thresholds as Record<string, unknown> | undefined) ?? {};
  const headerThreshold = asNumber(thresholds.header);
  const dataThreshold = asNumber(thresholds.data);
  const headerRow = asNumber(payload.header_row_index);
  const dataStart = asNumber(payload.data_row_start_index);
  const dataEnd = asNumber(payload.data_row_end_index);
  const trigger = (payload.trigger as Record<string, unknown> | undefined) ?? {};
  const triggerRow = asNumber(trigger.row_index);
  const headerScore = (trigger.scores as Record<string, unknown> | undefined)?.header ?? trigger.header_score;
  const dataScore = (trigger.scores as Record<string, unknown> | undefined)?.data ?? trigger.data_score;
  const headerScoreNum = asNumber(headerScore) ?? 0;
  const dataScoreNum = asNumber(dataScore) ?? 0;
  const contributions = Array.isArray(trigger.contributions)
    ? (trigger.contributions as Array<Record<string, unknown>>)
    : [];
  const contribPreview = contributions
    .flatMap((entry) => {
      const detector = shortName(entry.detector as string);
      const scores = (entry.scores as Record<string, unknown> | undefined) ?? {};
      return Object.entries(scores).map(
        ([kind, value]) => `${detector} ${kind}:${formatScore(asNumber(value))}`,
      );
    })
    .sort()
    .slice(0, 3)
    .join("; ");
  const sample =
    Array.isArray(trigger.sample) && trigger.sample.length
      ? `Sample: ${trigger.sample.slice(0, 5).join(", ")}${trigger.sample.length > 5 ? "…" : ""}`
      : "";

  const primary = `Picked header row ${headerRow ?? "?"}, data rows ${dataStart ?? "?"}-${dataEnd ?? "?"}${triggerRow !== undefined ? ` (trigger ${triggerRow})` : ""}`;
  const secondary = `hdr ${formatScore(headerScoreNum)}${headerThreshold !== undefined ? `/${formatScore(headerThreshold)}` : ""} · data ${formatScore(dataScoreNum)}${dataThreshold !== undefined ? `/${formatScore(dataThreshold)}` : ""}`;
  const tertiary = contribPreview ? `Signals: ${contribPreview}` : sample;
  const level: WorkbenchConsoleLine["level"] =
    (headerThreshold !== undefined && headerScoreNum < headerThreshold) ||
    (dataThreshold !== undefined && dataScoreNum < dataThreshold)
      ? "warning"
      : "info";

  return {
    level,
    message: [primary, secondary, tertiary, sample && contribPreview ? sample : ""].filter(Boolean).join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatHookCheckpoint(
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const stage = (payload.stage as string | undefined) ?? "checkpoint";
  return {
    level: "info",
    message: `Hook checkpoint: ${stage}`,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatMappingChecked(
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const mapped = asNumber(payload.mapped_columns) ?? 0;
  const extra = asNumber(payload.extra_columns) ?? 0;
  const level: WorkbenchConsoleLine["level"] = mapped === 0 ? "warning" : mapped > 0 ? "success" : "info";
  return {
    level,
    message: `Mapping result: ${mapped} mapped, ${extra} extra`,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatRunSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const source = (payload.source as Record<string, unknown> | undefined) ?? {};
  const status = (source.status as string | undefined) ?? "completed";
  const failure = (source.failure as Record<string, unknown> | undefined) ?? undefined;
  const failureCode = (failure?.code as string | undefined) ?? undefined;
  const failureMessage = (failure?.message as string | undefined) ?? undefined;
  const failureStage = (failure?.stage as string | undefined) ?? undefined;
  const counts = (payload.counts as Record<string, unknown> | undefined) ?? {};
  const tables = asNumber((counts.tables as Record<string, unknown> | undefined)?.total);
  const files = asNumber((counts.files as Record<string, unknown> | undefined)?.total);
  const sheets = asNumber((counts.sheets as Record<string, unknown> | undefined)?.total);
  const rows = asNumber((counts.rows as Record<string, unknown> | undefined)?.total);
  const cols = asNumber((counts.columns as Record<string, unknown> | undefined)?.physical_total);
  const fieldsCounts = (counts.fields as Record<string, unknown> | undefined) ?? {};
  const mappedFields = asNumber(fieldsCounts.mapped);
  const totalFields = asNumber(fieldsCounts.total);
  const required = asNumber(fieldsCounts.required);
  const requiredUnmapped = asNumber(fieldsCounts.required_unmapped) ?? 0;
  const detailObj = (payload.details as Record<string, unknown> | undefined) ?? {};

  const fieldsList = Array.isArray(payload.fields) ? (payload.fields as Array<Record<string, unknown>>) : [];
  const unmappedFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const outputPath =
    typeof detailObj.output_path === "string"
      ? detailObj.output_path
      : Array.isArray(detailObj.output_paths) && detailObj.output_paths.length
        ? String(detailObj.output_paths[0])
        : null;

  const headlineParts = [
    `Run summary: ${status}`,
    failureStage ? `stage ${failureStage}` : null,
    failureCode ? `code ${failureCode}` : null,
  ].filter(Boolean);

  const countLine = [
    files !== undefined ? `files ${files}` : null,
    sheets !== undefined ? `sheets ${sheets}` : null,
    tables !== undefined ? `tables ${tables}` : null,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const fieldLine =
    totalFields !== undefined && mappedFields !== undefined
      ? `mapped fields ${mappedFields}/${totalFields}${required !== undefined ? ` · required missing ${requiredUnmapped}/${required}` : ""}`
      : required !== undefined
        ? `required missing ${requiredUnmapped}/${required}`
        : null;

  const details: string[] = [];
  if (failureMessage) {
    details.push(`Failure: ${failureMessage}`);
  }
  if (unmappedFields.length) {
    details.push(`Unmapped fields: ${unmappedFields.join(", ")}`);
  }
  if (outputPath) {
    details.push(`Output: ${outputPath}`);
  }

  const messageLines = [
    headlineParts.join(" · "),
    countLine,
    fieldLine,
    details.join(" · "),
  ].filter((line) => line && line.length > 0);

  const level: WorkbenchConsoleLine["level"] =
    status === "failed" || !!failureMessage
      ? "error"
      : requiredUnmapped > 0
        ? "warning"
        : status === "succeeded"
          ? "success"
          : "info";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatTableDetails(
  details: unknown,
  sourceFile: string | undefined,
): string | null {
  if (!details || typeof details !== "object") {
    return sourceFile ? basename(sourceFile) : null;
  }
  const detailObj = details as Record<string, unknown>;
  const headerRow = asNumber(detailObj.header_row);
  const first = asNumber(detailObj.first_data_row);
  const last = asNumber(detailObj.last_data_row);
  const pieces: string[] = [];
  if (headerRow !== undefined) {
    pieces.push(`header row ${headerRow}`);
  }
  if (first !== undefined && last !== undefined) {
    pieces.push(`data ${first}-${last}`);
  }
  if (sourceFile) {
    pieces.push(basename(sourceFile));
  }
  return pieces.length ? pieces.join(" · ") : null;
}

function buildRunOutputUrl(runId: string | null): string | null {
  if (!runId) return null;
  const encodedRun = encodeURIComponent(runId);
  return `/api/v1/runs/${encodedRun}/output`;
}

function basename(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return "";
  const parts = trimmed.split("/");
  return parts[parts.length - 1] || trimmed;
}

function collectMissingRequired(payload: Record<string, unknown>): string[] {
  const mapping = payload?.mapping;
  const mapped =
    mapping &&
    typeof mapping === "object" &&
    Array.isArray((mapping as Record<string, unknown>).mapped_columns)
      ? ((mapping as Record<string, unknown>).mapped_columns as Array<Record<string, unknown>>)
      : Array.isArray(payload.mapped_fields)
        ? (payload.mapped_fields as Array<Record<string, unknown>>)
        : [];
  return mapped
    .filter((entry) => entry && typeof entry === "object" && entry.is_required === true && entry.is_satisfied === false)
    .map((entry) => (typeof entry.field === "string" && entry.field.trim()) || "")
    .filter(Boolean);
}

function collectUnmappedHeaders(payload: Record<string, unknown>): string[] {
  const fromRoot = Array.isArray(payload.unmapped_columns)
    ? (payload.unmapped_columns as Array<Record<string, unknown>>)
    : [];
  const fromMapping =
    payload.mapping &&
    typeof payload.mapping === "object" &&
    Array.isArray((payload.mapping as Record<string, unknown>).unmapped_columns)
      ? ((payload.mapping as Record<string, unknown>).unmapped_columns as Array<Record<string, unknown>>)
      : [];
  const combined = [...fromRoot, ...fromMapping];
  return combined
    .map((entry) => (entry && typeof entry === "object" ? (entry.header as string | undefined) : undefined))
    .map((header) => (header ?? "").trim())
    .filter(Boolean);
}

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "0.0%";
  return `${(Math.round(value * 10) / 10).toFixed(1)}%`;
}

function formatList(values: string[], maxEntries: number): string {
  if (!values.length) return "";
  const shown = values.slice(0, maxEntries);
  const remaining = values.length - shown.length;
  const suffix = remaining > 0 ? `... (+${remaining} more)` : "";
  return `${shown.join(", ")}${suffix}`;
}

function formatColumnDetectorScoreNumber(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "0.00";
  return (Math.round(value * 100) / 100).toFixed(2);
}

function formatScore(value?: number | null): string {
  return formatColumnDetectorScoreNumber(value);
}

function shortName(value?: string | null): string {
  if (!value) return "";
  const parts = value.split(".");
  return parts[parts.length - 1] || value;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return undefined;
  }
  return value;
}

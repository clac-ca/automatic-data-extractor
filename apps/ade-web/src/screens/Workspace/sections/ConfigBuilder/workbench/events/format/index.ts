import { eventName, eventTimestamp, isEventRecord } from "@shared/runs/types";
import type { RunStreamEvent } from "@shared/runs/types";

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

type EventFormatter = (
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
) => WorkbenchConsoleLine;
type PrefixFormatter = (
  event: RunStreamEvent,
  type: string,
  payload: Record<string, unknown>,
  timestamp: string,
) => WorkbenchConsoleLine;
type PrefixHandler = { prefix: string; formatter: PrefixFormatter };

const BUILD_EVENT_HANDLERS: Record<string, EventFormatter> = {
  "build.created": (_event, payload, timestamp) => formatBuildCreated(payload, timestamp),
  "build.queued": (_event, payload, timestamp) => formatBuildQueued(payload, timestamp),
  "build.start": (_event, payload, timestamp) => formatBuildStarted(payload, timestamp),
  "build.progress": (_event, payload, timestamp) => formatBuildProgress(payload, timestamp),
  "build.phase.start": (_event, payload, timestamp) => formatBuildPhaseStarted(payload, timestamp),
  "build.phase.complete": (_event, payload, timestamp) => formatBuildPhaseCompleted(payload, timestamp),
  "build.complete": (_event, payload, timestamp) => formatBuildCompletion(payload, timestamp),
};

const RUN_EVENT_HANDLERS: Record<string, EventFormatter> = {
  "run.queued": (event, payload, timestamp) => formatRunQueued(event, payload, timestamp),
  "run.waiting_for_build": (event, payload, timestamp) => formatRunWaitingForBuild(event, payload, timestamp),
  "run.start": (event, payload, timestamp) => formatRunStarted(event, payload, timestamp),
  "engine.start": (event, payload, timestamp) => formatRunStarted(event, payload, timestamp),
  "engine.phase.start": (event, payload, timestamp) => formatRunPhaseStarted(event, payload, timestamp),
  "engine.phase.complete": (event, payload, timestamp) => formatRunPhaseCompleted(event, payload, timestamp),
  "engine.table.summary": (event, payload, timestamp) => formatRunTableSummary(event, payload, timestamp),
  "engine.detector.column.score": (event, payload, timestamp) => formatColumnDetectorScore(event, payload, timestamp),
  "engine.detector.row.score": (event, payload, timestamp) => formatRowDetectorScore(event, payload, timestamp),
  "engine.file.summary": (event, payload, timestamp) => formatFileSummary(event, payload, timestamp),
  "engine.sheet.summary": (event, payload, timestamp) => formatSheetSummary(event, payload, timestamp),
  "engine.validation.issue": (event, payload, timestamp) => formatValidationIssue(event, payload, timestamp),
  "engine.validation.summary": (event, payload, timestamp) => formatValidationSummary(event, payload, timestamp),
  "engine.row_detector.result": (event, payload, timestamp) => formatEngineRowDetectorResult(event, payload, timestamp),
  "engine.row_classification": (event, payload, timestamp) => formatEngineRowClassification(event, payload, timestamp),
  "engine.column_detector.result": (event, payload, timestamp) => formatEngineColumnDetectorResult(event, payload, timestamp),
  "engine.column_detector.candidate": (event, payload, timestamp) => formatEngineColumnDetectorCandidate(event, payload, timestamp),
  "engine.column_classification": (event, payload, timestamp) => formatEngineColumnClassification(event, payload, timestamp),
  "engine.config.loaded": (event, payload, timestamp) => formatEngineConfigLoaded(event, payload, timestamp),
  "engine.log": (event, payload, timestamp) => formatEngineLog(event, payload, timestamp),
  "engine.table.written": (event, payload, timestamp) => formatEngineTableWritten(event, payload, timestamp),
  "run.error": (event, payload, timestamp) => formatRunError(event, payload, timestamp),
  "run.complete": (event, payload, timestamp) => formatRunCompletionOrSummary(event, payload, timestamp),
  "engine.complete": (event, payload, timestamp) => formatRunCompletionOrSummary(event, payload, timestamp),
  "engine.run.summary": (event, payload, timestamp) => formatRunCompletionOrSummary(event, payload, timestamp),
};

const RUN_PREFIX_HANDLERS: PrefixHandler[] = [
  { prefix: "config.", formatter: (event, type, payload, timestamp) => formatConfigEvent(event, type, payload, timestamp) },
  { prefix: "run.transform.", formatter: (event, type, payload, timestamp) => formatTransformEvent(event, type, payload, timestamp) },
];

export function formatConsoleEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  return isBuildEvent(event) ? formatBuildEvent(event) : formatRunEvent(event);
}

export { formatConsoleTimestamp } from "./common";

// --------------------------------------------------------------------------- //
// Build events
// --------------------------------------------------------------------------- //

export function formatBuildEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isEventRecord(event)) {
    return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" });
  }
  const payload = payloadOf(event);
  const ts = timestampLabel(event);
  const type = eventName(event);

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

function formatBuildCompletion(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const statusRaw = (payload.status as string | undefined) ?? "completed";
  const status = statusRaw === "ready" ? "succeeded" : statusRaw;
  const summary = (payload.summary as string | undefined)?.trim();
  const execution = (payload.execution as Record<string, unknown> | undefined) ?? {};
  const exitCode = typeof execution.exit_code === "number" ? execution.exit_code : undefined;
  const failure = (payload.failure as Record<string, unknown> | undefined) ?? undefined;
  const failureMessage = typeof failure?.message === "string" ? failure.message.trim() : undefined;

  if (status === "succeeded" || status === "reused" || status === "ready") {
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
      message: (failureMessage || summary || "Build failed.") + exit,
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

function formatBuildQueued(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? undefined;
  return {
    level: "info",
    message: reason ? `Build queued (${reason}).` : "Build queued.",
    timestamp,
    origin: "build",
  };
}

function formatBuildCreated(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? "queued";
  return {
    level: "info",
    message: `Build queued (${reason}).`,
    timestamp,
    origin: "build",
  };
}

function formatBuildStarted(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const reason = (payload.reason as string | undefined) ?? undefined;
  return {
    level: "info",
    message: reason ? `Build started (${reason}).` : "Build started.",
    timestamp,
    origin: "build",
  };
}

function formatBuildPhaseStarted(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "building";
  const message = (event.message as string | undefined)?.trim() ?? `Starting ${phase}`;
  return { level: "info", message, timestamp, origin: "build" };
}

function formatBuildProgress(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const message =
    (event.message as string | undefined)?.trim() ??
    ((payload.step as string | undefined) ? `Build: ${payload.step as string}` : "Build progress");
  return { level: "info", message, timestamp, origin: "build" };
}

function formatBuildPhaseCompleted(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "build";
  const status = (payload.status as string | undefined) ?? "completed";
  const duration = formatDurationMs(payload.duration_ms);
  const message =
    (event.message as string | undefined)?.trim() ??
    `${phase} ${status}${duration ? ` in ${duration}` : ""}`;
  const level: WorkbenchConsoleLine["level"] =
    status === "failed" ? "error" : status === "skipped" ? "warning" : "success";
  return { level, message, timestamp, origin: "build" };
}

// --------------------------------------------------------------------------- //
// Run/config/engine events
// --------------------------------------------------------------------------- //

export function formatRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isEventRecord(event)) {
    return withRaw(event, { level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" });
  }
  const payload = payloadOf(event);
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const type = eventName(event);

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

function formatRunQueued(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const mode = (payload.mode as string | undefined) ?? undefined;
  const runId =
    (payload.jobId as string | undefined) ??
    (payload.run_id as string | undefined) ??
    "";
  const suffix = mode ? ` (${mode})` : "";
  return {
    level: "info",
    message: `Run ${runId ? `${runId} ` : ""}queued${suffix}.`,
    timestamp,
    origin: "run",
  };
}

function formatRunWaitingForBuild(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
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

function formatRunStarted(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
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

function formatRunPhaseStarted(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "progress";
  const message = (event.message as string | undefined)?.trim() ?? `Phase: ${phase}`;
  const level = normalizeLevel((payload.level as string | undefined) ?? "info");
  return {
    level,
    message,
    timestamp,
    origin: "run",
  };
}

function formatRunPhaseCompleted(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const phase = (payload.phase as string | undefined) ?? "phase";
  const status = (payload.status as string | undefined) ?? "completed";
  const duration = formatDurationMs(payload.duration_ms);
  const message =
    (event.message as string | undefined)?.trim() ??
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

function formatRunTableSummary(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  if (isAdeSummary(payload, "table")) {
    return formatTableSummary(payload, timestamp);
  }
  return formatLegacyTableSummary(payload, timestamp);
}

function formatValidationIssue(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const sev = (payload.severity as string | undefined) ?? "info";
  return {
    level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
    message: `Validation issue${payload.code ? `: ${payload.code as string}` : ""}`,
    timestamp,
    origin: "run",
  };
}

function formatValidationSummary(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
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

function formatRunError(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const code = (payload.code as string | undefined) ?? "unknown_error";
  const message = (event.message as string | undefined)?.trim() ?? "Run error.";
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
  const runId =
    (payload.jobId as string | undefined) ??
    (payload.run_id as string | undefined) ??
    null;
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

function formatEngineConfigLoaded(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const pkg = (payload.config_package as string | undefined) ?? "config";
  const fields = Array.isArray(payload.fields) ? payload.fields.length : undefined;
  const message = fields !== undefined ? `Config loaded (${pkg}, fields=${fields})` : `Config loaded (${pkg})`;
  return { level: "info", message, timestamp, origin: "run", raw: payload };
}

function formatEngineLog(event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const level = normalizeLevel((payload.level as string | undefined) ?? (event.level as string | undefined) ?? "info");
  const msgFromEvent = typeof event.message === "string" ? event.message.trim() : "";
  const fallback = typeof payload.text === "string" ? payload.text : "";
  const message = msgFromEvent || fallback || "Engine log";
  return { level, message, timestamp, origin: "run", raw: event };
}

function formatEngineTableWritten(_event: RunStreamEvent, payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const sheet = (payload.sheet_name as string | undefined) ?? "sheet";
  const tableIndex = typeof payload.table_index === "number" ? payload.table_index : null;
  const output = (payload.output_range as string | undefined) ?? undefined;
  const message = `Table${tableIndex !== null ? ` #${tableIndex}` : ""} written on ${sheet}${output ? ` (${output})` : ""}`;
  return { level: "info", message, timestamp, origin: "run", raw: payload };
}

function formatEngineRowDetectorResult(
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const level = normalizeLevel(event.level ?? "info");
  const sheet = (payload.sheet_name as string | undefined) ?? "sheet";
  const rowIndex = payload.row_index as number | undefined;
  const detector = (payload.detector as Record<string, unknown> | undefined) ?? {};
  const name = (detector.name as string | undefined) ?? "detector";
  const scores = formatScores(detector.scores as Record<string, unknown> | undefined);
  const message = scores
    ? `Row ${rowIndex ?? "?"} detector ${name} on ${sheet} (${scores})`
    : `Row ${rowIndex ?? "?"} detector ${name} on ${sheet}`;
  return { level, message, timestamp, origin: "run" };
}

function formatEngineRowClassification(
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const level = normalizeLevel(event.level ?? "info");
  const sheet = (payload.sheet_name as string | undefined) ?? "sheet";
  const rowIndex = payload.row_index as number | undefined;
  const classification = (payload.classification as Record<string, unknown> | undefined) ?? {};
  const kind = (classification.row_kind as string | undefined) ?? "unknown";
  const score = typeof classification.score === "number" ? classification.score : undefined;
  const message = `Row ${rowIndex ?? "?"} → ${kind}${score !== undefined ? ` (${score.toFixed(3)})` : ""} on ${sheet}`;
  return { level, message, timestamp, origin: "run" };
}

function formatEngineColumnDetectorResult(
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const level = normalizeLevel(event.level ?? "info");
  const sheet = (payload.sheet_name as string | undefined) ?? "sheet";
  const columnIndex = payload.column_index as number | undefined;
  const detector = (payload.detector as Record<string, unknown> | undefined) ?? {};
  const name = (detector.name as string | undefined) ?? "detector";
  const scores = formatScores(detector.scores as Record<string, unknown> | undefined);
  const message = scores
    ? `Column ${columnIndex ?? "?"} detector ${name} on ${sheet} (${scores})`
    : `Column ${columnIndex ?? "?"} detector ${name} on ${sheet}`;
  return { level, message, timestamp, origin: "run" };
}

function formatEngineColumnClassification(
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const level = normalizeLevel(event.level ?? "info");
  const sheet = (payload.sheet_name as string | undefined) ?? "sheet";
  const columnIndex = payload.column_index as number | undefined;
  const classification = (payload.classification as Record<string, unknown> | undefined) ?? {};
  const field = (classification.field as string | undefined) ?? "unknown";
  const score = typeof classification.score === "number" ? classification.score : undefined;
  const message = `Column ${columnIndex ?? "?"} classified as ${field}${score !== undefined ? ` (score=${score.toFixed(3)})` : ""} on ${sheet}`;
  return { level, message, timestamp, origin: "run" };
}

function formatEngineColumnDetectorCandidate(
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const level = normalizeLevel(event.level ?? "info");
  const columnIndex = payload.column_index as number | undefined;
  const header = (payload.header as string | undefined) ?? undefined;
  const bestField = (payload.best_field as string | undefined) ?? "unknown";
  const bestScore = typeof payload.best_score === "number" ? payload.best_score : undefined;
  const scores = formatScores(payload.scores as Record<string, unknown> | undefined);
  const messageParts = [
    `Column ${columnIndex ?? "?"} candidate ${bestField}`,
    bestScore !== undefined ? `(score=${bestScore.toFixed(3)})` : null,
    header ? `header="${header}"` : null,
    scores ? `scores: ${scores}` : null,
  ].filter(Boolean);
  const message = messageParts.join(" · ");
  return { level, message, timestamp, origin: "run" };
}

function formatScores(scores?: Record<string, unknown>): string | null {
  if (!scores || typeof scores !== "object") return null;
  const entries = Object.entries(scores).filter(([, value]) => typeof value === "number");
  if (!entries.length) return null;
  return entries
    .slice(0, 3)
    .map(([key, value]) => `${key}=${(value as number).toFixed(3)}`)
    .join(", ");
}

function withRaw(event: RunStreamEvent, line: WorkbenchConsoleLine): WorkbenchConsoleLine {
  return { ...line, raw: event };
}

function formatConfigEvent(
  event: RunStreamEvent,
  type: string,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const message =
    (event.message as string | undefined)?.trim() ?? `Config event: ${type.replace(/^config\\./, "")}`;
  return {
    level: normalizeLevel((payload.level as string | undefined) ?? "info"),
    message,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatTransformEvent(
  event: RunStreamEvent,
  type: string,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const phase = type.replace("run.transform.", "");
  const level = normalizeLevel((payload.level as string | undefined) ?? "info");
  const message =
    (event.message as string | undefined)?.trim() ??
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
    `Table summary: ${sheet}`,
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
  return `/api/v1/runs/${encodedRun}/output/download`;
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

import { eventTimestamp, isAdeEvent } from "@shared/runs/types";
import type { AdeEvent as RunStreamEvent } from "@shared/runs/types";

import type { WorkbenchConsoleLine } from "../types";

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
};

export function formatConsoleTimestamp(value: string | Date): string {
  const iso =
    value instanceof Date
      ? Number.isNaN(value.getTime())
        ? null
        : value.toISOString()
      : value;
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], TIME_OPTIONS);
}

export function describeBuildEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  const attachRaw = (line: WorkbenchConsoleLine): WorkbenchConsoleLine => ({ ...line, raw: event });

  if (!isAdeEvent(event)) {
    return attachRaw({ level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" });
  }
  const payload = payloadOf(event);
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const type = event.type;

  if (type === "console.line") {
    return attachRaw(formatConsole(event, payload, ts, "build"));
  }

  if (!type?.startsWith("build.")) {
    return attachRaw({
      level: "info",
      message: JSON.stringify(event),
      timestamp: ts,
      origin: "build",
    });
  }

  switch (type) {
    case "build.queued": {
      const reason = (payload.reason as string | undefined) ?? undefined;
      return attachRaw({
        level: "info",
        message: reason ? `Build queued (${reason}).` : "Build queued.",
        timestamp: ts,
        origin: "build",
      });
    }
    case "build.created": {
      const reason = (payload.reason as string | undefined) ?? "queued";
      return attachRaw({
        level: "info",
        message: `Build queued (${reason}).`,
        timestamp: ts,
        origin: "build",
      });
    }
    case "build.started":
    case "build.start": {
      const reason = (payload.reason as string | undefined) ?? undefined;
      return attachRaw({
        level: "info",
        message: reason ? `Build started (${reason}).` : "Build started.",
        timestamp: ts,
        origin: "build",
      });
    }
    case "build.phase.started":
    case "build.phase.start": {
      const phase = (payload.phase as string | undefined) ?? "building";
      const message = (payload.message as string | undefined) ?? `Starting ${phase}`;
      return attachRaw({ level: "info", message, timestamp: ts, origin: "build" });
    }
    case "build.progress": {
      const message =
        (payload.message as string | undefined) ??
        ((payload.step as string | undefined) ? `Build: ${payload.step as string}` : "Build progress");
      return attachRaw({ level: "info", message, timestamp: ts, origin: "build" });
    }
    case "build.phase.completed":
    case "build.phase.complete": {
      const phase = (payload.phase as string | undefined) ?? "build";
      const status = (payload.status as string | undefined) ?? "completed";
      const duration = formatDurationMs(payload.duration_ms);
      const message =
        (payload.message as string | undefined) ??
        `${phase} ${status}${duration ? ` in ${duration}` : ""}`;
      const level: WorkbenchConsoleLine["level"] =
        status === "failed" ? "error" : status === "skipped" ? "warning" : "success";
      return attachRaw({ level, message, timestamp: ts, origin: "build" });
    }
    case "build.completed":
    case "build.complete":
      return attachRaw(formatBuildCompletion(payload, ts));
    default:
      return attachRaw({ level: "info", message: JSON.stringify(event), timestamp: ts, origin: "build" });
  }
}

export function describeRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  const attachRaw = (line: WorkbenchConsoleLine): WorkbenchConsoleLine => ({ ...line, raw: event });

  if (!isAdeEvent(event)) {
    return attachRaw({ level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" });
  }
  const payload = payloadOf(event);
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const type = event.type;

  if (type === "console.line") {
    return attachRaw(
      formatConsole(event, payload, ts, (payload.scope as string | undefined) === "build" ? "build" : "run"),
    );
  }

  if (!type?.startsWith("run.") && !type?.startsWith("engine.") && !type?.startsWith("config.")) {
    return attachRaw({ level: "info", message: JSON.stringify(event), timestamp: ts, origin: "run" });
  }

  switch (type) {
    case "run.queued": {
      const mode = (payload.mode as string | undefined) ?? undefined;
      const runId = event.run_id ?? "";
      const suffix = mode ? ` (${mode})` : "";
      return attachRaw({
        level: "info",
        message: `Run ${runId ? `${runId} ` : ""}queued${suffix}.`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.waiting_for_build": {
      const reason = (payload.reason as string | undefined) ?? undefined;
      const buildId = (payload.build_id as string | undefined) ?? undefined;
      const reasonPart = reason ? ` (${reason})` : "";
      const buildPart = buildId ? ` · ${buildId}` : "";
      return attachRaw({
        level: "info",
        message: `Waiting for build${reasonPart}${buildPart}.`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.started":
    case "run.start":
    case "engine.start": {
      const mode = (payload.mode as string | undefined) ?? undefined;
      const env = (payload.env as { reused?: boolean; reason?: string } | undefined) ?? undefined;
      const envNote = env?.reused ? " (reused environment)" : env?.reason ? ` (${env.reason})` : "";
      return attachRaw({
        level: "info",
        message: `Run started${mode ? ` (${mode})` : ""}${envNote}.`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.phase.started":
    case "run.phase.start":
    case "engine.phase.start": {
      const phase = (payload.phase as string | undefined) ?? "progress";
      const message = (payload.message as string | undefined) ?? `Phase: ${phase}`;
      const level = normalizeLevel((payload.level as string | undefined) ?? "info");
      return attachRaw({
        level,
        message,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.phase.completed":
    case "run.phase.complete":
    case "engine.phase.complete": {
      const phase = (payload.phase as string | undefined) ?? "phase";
      const status = (payload.status as string | undefined) ?? "completed";
      const duration = formatDurationMs(payload.duration_ms);
      const message =
        (payload.message as string | undefined) ??
        `Phase ${phase} ${status}${duration ? ` in ${duration}` : ""}`;
      const level: WorkbenchConsoleLine["level"] =
        status === "failed" ? "error" : status === "skipped" ? "warning" : "success";
      return attachRaw({
        level,
        message,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.table.summary":
    case "engine.table.summary": {
      if (isAdeSummary(payload, "table")) {
        return attachRaw(formatTableSummary(payload, ts));
      }
      return attachRaw(formatLegacyTableSummary(payload, ts));
    }
    case "run.column_detector.score":
    case "engine.detector.column.score":
      return attachRaw(formatColumnDetectorScore(payload, ts));
    case "run.row_detector.score":
    case "engine.detector.row.score":
      return attachRaw(formatRowDetectorScore(payload, ts));
    case "run.hook.checkpoint":
      return attachRaw(formatHookCheckpoint(payload, ts));
    case "run.hook.mapping_checked":
      return attachRaw(formatMappingChecked(payload, ts));
    case "engine.file.summary":
      return attachRaw(formatFileSummary(payload, ts));
    case "engine.sheet.summary":
      return attachRaw(formatSheetSummary(payload, ts));
    case "run.validation.issue":
    case "engine.validation.issue": {
      const sev = (payload.severity as string | undefined) ?? "info";
      return attachRaw({
        level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
        message: `Validation issue${payload.code ? `: ${payload.code as string}` : ""}`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.validation.summary":
    case "engine.validation.summary": {
      const total = (payload.issues_total as number | undefined) ?? 0;
      const maxSeverity = (payload.max_severity as string | undefined) ?? undefined;
      const level: WorkbenchConsoleLine["level"] =
        maxSeverity === "error" ? "error" : maxSeverity === "warning" || total > 0 ? "warning" : "info";
      const descriptor = maxSeverity ? `${maxSeverity}` : total > 0 ? "issues" : "clean";
      return attachRaw({
        level,
        message: `Validation summary: ${total} ${descriptor}`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.error": {
      const code = (payload.code as string | undefined) ?? "unknown_error";
      const message = (payload.message as string | undefined) ?? "Run error.";
      const stage = (payload.stage as string | undefined) ?? (payload.phase as string | undefined);
      const stageLabel = stage ? ` [${stage}]` : "";
      return attachRaw({
        level: "error",
        message: `${message}${stageLabel} (${code})`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.complete":
    case "engine.complete":
    case "engine.run.summary":
      if (isAdeSummary(payload, "run")) {
        return attachRaw(formatRunSummary(payload, ts));
      }
      return attachRaw(formatRunCompletion(payload, ts));
    default:
      if (type.startsWith("config.")) {
        return attachRaw(formatConfigEvent(type, payload, ts));
      }
      if (type.startsWith("run.transform.")) {
        return attachRaw(formatTransformEvent(type, payload, ts));
      }
      return attachRaw({ level: "info", message: JSON.stringify(event), timestamp: ts, origin: "run" });
  }
}

function formatConsole(
  event: RunStreamEvent,
  payload: Record<string, unknown>,
  timestamp: string,
  overrideOrigin?: WorkbenchConsoleLine["origin"],
): WorkbenchConsoleLine {
  const stream = payload.stream as string | undefined;
  const level = (payload.level as string | undefined) ?? (stream === "stderr" ? "warning" : "info");
  const message =
    (payload.message as string | undefined) ??
    (typeof payload.text === "string" ? payload.text : JSON.stringify(payload));
  const scope = (payload.scope as string | undefined) ?? undefined;
  const origin: WorkbenchConsoleLine["origin"] =
    overrideOrigin ?? (scope === "build" ? "build" : "run");

  return {
    level: normalizeLevel(level),
    message: String(message ?? ""),
    timestamp,
    origin,
    raw: event,
  };
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

function formatRunCompletion(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
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
  return {
    level,
    message: `${base}${exitPart}.`,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function normalizeLevel(level?: string): WorkbenchConsoleLine["level"] {
  if (level === "error") return "error";
  if (level === "warning" || level === "warn") return "warning";
  if (level === "success") return "success";
  return "info";
}

function payloadOf(event: RunStreamEvent): Record<string, unknown> {
  const payload = event.payload;
  if (payload && typeof payload === "object") {
    return payload as Record<string, unknown>;
  }
  return {};
}

function formatDurationMs(value?: unknown): string | null {
  if (typeof value !== "number" || Number.isNaN(value) || value < 0) {
    return null;
  }
  if (value < 1000) {
    return `${Math.round(value)} ms`;
  }
  if (value < 60_000) {
    return `${(value / 1000).toFixed(1)} s`;
  }
  const minutes = Math.floor(value / 60_000);
  const seconds = Math.round((value % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return undefined;
  }
  return value;
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

function basename(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return "";
  const parts = trimmed.split("/");
  return parts[parts.length - 1] || trimmed;
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

  const fieldsList = Array.isArray(payload.fields) ? (payload.fields as Array<Record<string, unknown>>) : [];
  const unmappedFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const outputs = Array.isArray((payload.details as Record<string, unknown> | undefined)?.output_paths)
    ? ((payload.details as Record<string, unknown>).output_paths as string[])
    : [];

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
  if (outputs.length) {
    details.push(`Outputs: ${outputs.join(", ")}`);
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
  const unmappedFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const columns = Array.isArray(payload.columns) ? (payload.columns as Array<Record<string, unknown>>) : [];
  const unmappedHeaders = columns
    .filter((c) => c && typeof c === "object" && c.mapped === false)
    .map((c) => (c.header as string | undefined) ?? "")
    .map((h) => h.trim())
    .filter((h) => h.length > 0);
  const headerPreview = unmappedHeaders.length ? unmappedHeaders.join(", ") : "";
  const unmappedFieldPreview = unmappedFields.length ? unmappedFields.join(", ") : "";

  const headlineParts = [
    `File summary: ${fileName}`,
    sheets !== undefined ? `sheets ${sheets}` : null,
    tables !== undefined ? `tables ${tables}` : null,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
    totalFields !== undefined && mappedFields !== undefined ? `mapped fields ${mappedFields}/${totalFields}` : null,
    required !== undefined && requiredUnmapped !== undefined ? `required missing ${requiredUnmapped}/${required}` : null,
  ].filter(Boolean);

  const details: string[] = [];
  if (mappedHeaders !== undefined && totalHeaders !== undefined) {
    details.push(`headers mapped ${mappedHeaders}/${totalHeaders}`);
  }
  if (headerPreview) {
    details.push(`Unmapped headers: ${headerPreview}`);
  }
  if (unmappedFieldPreview) {
    details.push(`Unmapped fields: ${unmappedFieldPreview}`);
  }
  if (unmappedRequiredFields.length) {
    details.push(`Required fields unmapped: ${unmappedRequiredFields.join(", ")}`);
  }

  const ids = (payload.details as Record<string, unknown> | undefined) ?? {};
  const sheetIds = Array.isArray(ids.sheet_ids) ? ids.sheet_ids.join(", ") : undefined;
  const tableIds = Array.isArray(ids.table_ids) ? ids.table_ids.join(", ") : undefined;
  const idLine = [payload.id ? `id ${payload.id}` : null, sheetIds ? `sheets ${sheetIds}` : null, tableIds ? `tables ${tableIds}` : null]
    .filter(Boolean)
    .join(" · ");

  const messageLines = [headlineParts.join(" · "), details.join(" · "), idLine ? `(${idLine})` : null]
    .filter((line) => line && line.length > 0);

  const level: WorkbenchConsoleLine["level"] =
    requiredUnmapped > 0 ? "error" : unmappedHeaders.length > 0 || unmappedFields.length > 0 ? "warning" : "success";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatTableSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const source = (payload.source as Record<string, unknown> | undefined) ?? {};
  const sheetName = (source.sheet_name as string | undefined) ?? "table";
  const tableIndex = asNumber(source.table_index);
  const fileName = source.file_path ? basename(source.file_path as string) : undefined;
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
  const unmappedFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const columns = Array.isArray(payload.columns) ? (payload.columns as Array<Record<string, unknown>>) : [];
  const unmappedHeaders = columns
    .filter((c) => c && typeof c === "object" && c.mapped === false)
    .map((c) => (c.header as string | undefined) ?? "")
    .map((h) => h.trim())
    .filter((h) => h.length > 0);
  const headerPreview = unmappedHeaders.length ? unmappedHeaders.join(", ") : "";
  const unmappedFieldPreview = unmappedFields.length ? unmappedFields.join(", ") : "";

  const headlineParts = [
    `Table summary: ${sheetName}${tableIndex !== undefined ? ` (table ${tableIndex})` : ""}`,
    fileName ? `file ${fileName}` : null,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
    totalFields !== undefined && mappedFields !== undefined ? `mapped fields ${mappedFields}/${totalFields}` : null,
    required !== undefined && requiredUnmapped !== undefined ? `required missing ${requiredUnmapped}/${required}` : null,
  ].filter(Boolean);

  const details: string[] = [];
  if (mappedHeaders !== undefined && totalHeaders !== undefined) {
    details.push(`headers mapped ${mappedHeaders}/${totalHeaders}`);
  }
  if (outputSheet) {
    details.push(`output sheet ${outputSheet}`);
  }
  if (headerPreview) {
    details.push(`Unmapped headers: ${headerPreview}`);
  }
  if (unmappedFieldPreview) {
    details.push(`Unmapped fields: ${unmappedFieldPreview}`);
  }

  const metaDetails = (payload.details as Record<string, unknown> | undefined) ?? {};
  const headerRow = asNumber(metaDetails.header_row_index ?? metaDetails.header_row);
  const dataStart = asNumber(metaDetails.first_data_row_index ?? metaDetails.first_data_row);
  const dataEnd = asNumber(metaDetails.last_data_row_index ?? metaDetails.last_data_row);
  const position =
    headerRow !== undefined || dataStart !== undefined || dataEnd !== undefined
      ? `header row ${headerRow ?? "?"}${dataStart !== undefined || dataEnd !== undefined ? ` · data ${dataStart ?? "?"}-${dataEnd ?? "?"}` : ""}`
      : null;
  const idLine = [
    payload.id ? `id ${payload.id}` : null,
    position,
  ]
    .filter(Boolean)
    .join(" · ");

  const messageLines = [headlineParts.join(" · "), details.join(" · "), idLine ? `(${idLine})` : null]
    .filter((line) => line && line.length > 0);

  const level: WorkbenchConsoleLine["level"] =
    requiredUnmapped > 0 ? "error" : unmappedHeaders.length > 0 || unmappedFields.length > 0 ? "warning" : "success";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatSheetSummary(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const source = (payload.source as Record<string, unknown> | undefined) ?? {};
  const sheetName = (source.sheet_name as string | undefined) ?? "sheet";
  const fileName = source.file_path ? basename(source.file_path as string) : undefined;
  const counts = (payload.counts as Record<string, unknown> | undefined) ?? {};
  const rows = asNumber((counts.rows as Record<string, unknown> | undefined)?.total);
  const cols = asNumber((counts.columns as Record<string, unknown> | undefined)?.physical_total);
  const tables = asNumber((counts.tables as Record<string, unknown> | undefined)?.total);
  const fields = (counts.fields as Record<string, unknown> | undefined) ?? {};
  const required = asNumber(fields.required);
  const requiredUnmapped = asNumber(fields.required_unmapped) ?? 0;
  const mappedFields = asNumber(fields.mapped);
  const totalFields = asNumber(fields.total);

  const headerCounts = (counts.columns as Record<string, unknown> | undefined) ?? {};
  const mappedHeaders = asNumber(headerCounts.distinct_headers_mapped);
  const totalHeaders = asNumber(headerCounts.distinct_headers);

  const fieldsList = Array.isArray(payload.fields) ? (payload.fields as Array<Record<string, unknown>>) : [];
  const unmappedFields = fieldsList
    .filter((f) => f && typeof f === "object" && f.mapped === false)
    .map((f) => (f.field as string | undefined) || (f.label as string | undefined))
    .filter(Boolean) as string[];

  const columns = Array.isArray(payload.columns) ? (payload.columns as Array<Record<string, unknown>>) : [];
  const unmappedHeaders = columns
    .filter((c) => c && typeof c === "object" && c.mapped === false)
    .map((c) => (c.header as string | undefined) ?? "")
    .map((h) => h.trim())
    .filter((h) => h.length > 0);
  const headerPreview = unmappedHeaders.length ? unmappedHeaders.join(", ") : "";
  const unmappedFieldPreview = unmappedFields.length ? unmappedFields.join(", ") : "";

  const headlineParts = [
    `Sheet summary: ${sheetName}`,
    fileName ? `file ${fileName}` : null,
    tables !== undefined ? `tables ${tables}` : null,
    rows !== undefined ? `rows ${rows}` : null,
    cols !== undefined ? `cols ${cols}` : null,
    totalFields !== undefined && mappedFields !== undefined ? `mapped fields ${mappedFields}/${totalFields}` : null,
    required !== undefined && requiredUnmapped !== undefined ? `required missing ${requiredUnmapped}/${required}` : null,
  ].filter(Boolean);

  const details: string[] = [];
  if (mappedHeaders !== undefined && totalHeaders !== undefined) {
    details.push(`headers mapped ${mappedHeaders}/${totalHeaders}`);
  }
  if (headerPreview) {
    details.push(`Unmapped headers: ${headerPreview}`);
  }
  if (unmappedFieldPreview) {
    details.push(`Unmapped fields: ${unmappedFieldPreview}`);
  }

  const ids = (payload.details as Record<string, unknown> | undefined) ?? {};
  const tableIds = Array.isArray(ids.table_ids) ? ids.table_ids.join(", ") : undefined;
  const idLine = [payload.id ? `id ${payload.id}` : null, tableIds ? `tables ${tableIds}` : null]
    .filter(Boolean)
    .join(" · ");

  const messageLines = [headlineParts.join(" · "), details.join(" · "), idLine ? `(${idLine})` : null]
    .filter((line) => line && line.length > 0);

  const level: WorkbenchConsoleLine["level"] =
    requiredUnmapped > 0 ? "error" : unmappedHeaders.length > 0 || unmappedFields.length > 0 ? "warning" : "success";

  return {
    level,
    message: messageLines.join("\n"),
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatScore(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "?";
  return value.toFixed(2);
}

function shortName(name?: string): string {
  if (!name) return "";
  const parts = name.split("."); // e.g., module.fn
  return parts[parts.length - 1] || name;
}

function isAdeSummary(payload: Record<string, unknown>, scope: "table" | "sheet" | "file"): boolean {
  if (!payload || typeof payload !== "object") return false;
  const schemaId = (payload.schema_id as string | undefined) ?? (payload.schema as string | undefined);
  const scopeValue = payload.scope as string | undefined;
  return schemaId === "ade.summary" && scopeValue === scope;
}

function formatTransformEvent(
  type: string,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const segments = type.split(".");
  const name = segments.slice(2).join(".") || "transform";
  const rowIndex = asNumber(payload.row_index);
  const message = `Transform: ${name}${rowIndex !== undefined ? ` (row ${rowIndex})` : ""}`;
  return {
    level: "info",
    message,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatConfigEvent(
  type: string,
  payload: Record<string, unknown>,
  timestamp: string,
): WorkbenchConsoleLine {
  const name = type.replace(/^config\./, "");
  const headline = `Config event: ${name}`;
  const payloadText = formatConfigPayload(payload);
  const message = payloadText ? `${headline}\n${payloadText}` : headline;

  return {
    level: "info",
    message,
    timestamp,
    origin: "run",
    raw: payload,
  };
}

function formatConfigPayload(payload: Record<string, unknown>): string {
  try {
    return JSON.stringify(payload ?? {}, null, 2);
  } catch {
    return String(payload ?? "");
  }
}

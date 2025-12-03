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
  const attachRaw = (line: WorkbenchConsoleLine): WorkbenchConsoleLine =>
    line.raw ? line : { ...line, raw: event };

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
    case "build.started": {
      const reason = (payload.reason as string | undefined) ?? undefined;
      return attachRaw({
        level: "info",
        message: reason ? `Build started (${reason}).` : "Build started.",
        timestamp: ts,
        origin: "build",
      });
    }
    case "build.phase.started": {
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
    case "build.phase.completed": {
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
      return attachRaw(formatBuildCompletion(payload, ts));
    default:
      return attachRaw({ level: "info", message: JSON.stringify(event), timestamp: ts, origin: "build" });
  }
}

export function describeRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  const attachRaw = (line: WorkbenchConsoleLine): WorkbenchConsoleLine =>
    line.raw ? line : { ...line, raw: event };

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

  if (!type?.startsWith("run.")) {
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
    case "run.started": {
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
    case "run.phase.started": {
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
    case "run.phase.completed": {
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
    case "run.table.summary": {
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

      return attachRaw({
        level,
        message: messageLines.join("\n"),
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.validation.issue": {
      const sev = (payload.severity as string | undefined) ?? "info";
      return attachRaw({
        level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
        message: `Validation issue${payload.code ? `: ${payload.code as string}` : ""}`,
        timestamp: ts,
        origin: "run",
      });
    }
    case "run.validation.summary": {
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
    case "run.completed":
      return attachRaw(formatRunCompletion(payload, ts));
    default:
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
  const status = (payload.status as string | undefined) ?? "completed";
  const execution = (payload.execution as Record<string, unknown> | undefined) ?? {};
  const exit = typeof execution.exit_code === "number" ? execution.exit_code : undefined;
  const failure = payload.failure as Record<string, unknown> | undefined;
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

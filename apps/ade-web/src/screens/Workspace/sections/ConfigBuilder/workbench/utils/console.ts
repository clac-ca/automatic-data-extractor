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
  if (!isAdeEvent(event)) {
    return { level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" };
  }
  const payload = payloadOf(event);
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const type = event.type;

  if (type === "console.line") {
    return formatConsole(event, payload, ts, "build");
  }

  if (!type?.startsWith("build.")) {
    return {
      level: "info",
      message: JSON.stringify(event),
      timestamp: ts,
      origin: "build",
    };
  }

  switch (type) {
    case "build.created": {
      const reason = (payload.reason as string | undefined) ?? "queued";
      return {
        level: "info",
        message: `Build queued (${reason}).`,
        timestamp: ts,
        origin: "build",
      };
    }
    case "build.started": {
      const reason = (payload.reason as string | undefined) ?? undefined;
      return {
        level: "info",
        message: reason ? `Build started (${reason}).` : "Build started.",
        timestamp: ts,
        origin: "build",
      };
    }
    case "build.phase.started": {
      const phase = (payload.phase as string | undefined) ?? "building";
      const message = (payload.message as string | undefined) ?? `Starting ${phase}`;
      return { level: "info", message, timestamp: ts, origin: "build" };
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
      return { level, message, timestamp: ts, origin: "build" };
    }
    case "build.completed":
      return formatBuildCompletion(payload, ts);
    default:
      return { level: "info", message: JSON.stringify(event), timestamp: ts, origin: "build" };
  }
}

export function describeRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isAdeEvent(event)) {
    return { level: "info", message: JSON.stringify(event), timestamp: "", origin: "raw" };
  }
  const payload = payloadOf(event);
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const type = event.type;

  if (type === "console.line") {
    return formatConsole(event, payload, ts, (payload.scope as string | undefined) === "build" ? "build" : "run");
  }

  if (!type?.startsWith("run.")) {
    return { level: "info", message: JSON.stringify(event), timestamp: ts, origin: "run" };
  }

  switch (type) {
    case "run.queued": {
      const mode = (payload.mode as string | undefined) ?? undefined;
      const runId = event.run_id ?? "";
      const suffix = mode ? ` (${mode})` : "";
      return {
        level: "info",
        message: `Run ${runId ? `${runId} ` : ""}queued${suffix}.`,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.started": {
      const mode = (payload.mode as string | undefined) ?? undefined;
      const env = (payload.env as { reused?: boolean; reason?: string } | undefined) ?? undefined;
      const envNote = env?.reused ? " (reused environment)" : env?.reason ? ` (${env.reason})` : "";
      return {
        level: "info",
        message: `Run started${mode ? ` (${mode})` : ""}${envNote}.`,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.phase.started": {
      const phase = (payload.phase as string | undefined) ?? "progress";
      const message = (payload.message as string | undefined) ?? `Phase: ${phase}`;
      const level = normalizeLevel((payload.level as string | undefined) ?? "info");
      return {
        level,
        message,
        timestamp: ts,
        origin: "run",
      };
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
      return {
        level,
        message,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.table.summary": {
      const name =
        (payload.source_sheet as string | undefined) ??
        (payload.source_file as string | undefined) ??
        (payload.table_id as string | undefined) ??
        "table";
      return {
        level: "info",
        message: `Table completed (${name})`,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.validation.issue": {
      const sev = (payload.severity as string | undefined) ?? "info";
      return {
        level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
        message: `Validation issue${payload.code ? `: ${payload.code as string}` : ""}`,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.validation.summary": {
      const total = (payload.issues_total as number | undefined) ?? 0;
      const maxSeverity = (payload.max_severity as string | undefined) ?? undefined;
      const level: WorkbenchConsoleLine["level"] =
        maxSeverity === "error" ? "error" : maxSeverity === "warning" || total > 0 ? "warning" : "info";
      const descriptor = maxSeverity ? `${maxSeverity}` : total > 0 ? "issues" : "clean";
      return {
        level,
        message: `Validation summary: ${total} ${descriptor}`,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.error": {
      const code = (payload.code as string | undefined) ?? "unknown_error";
      const message = (payload.message as string | undefined) ?? "Run error.";
      const stage = (payload.stage as string | undefined) ?? (payload.phase as string | undefined);
      const stageLabel = stage ? ` [${stage}]` : "";
      return {
        level: "error",
        message: `${message}${stageLabel} (${code})`,
        timestamp: ts,
        origin: "run",
      };
    }
    case "run.completed":
      return formatRunCompletion(payload, ts);
    default:
      return { level: "info", message: JSON.stringify(event), timestamp: ts, origin: "run" };
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
    };
  }
  if (status === "canceled") {
    return { level: "warning", message: "Build was canceled before completion.", timestamp, origin: "build" };
  }
  if (status === "failed") {
    const exit = typeof exitCode === "number" ? ` (exit code ${exitCode})` : "";
    return {
      level: "error",
      message: (errorMessage || summary || "Build failed.") + exit,
      timestamp,
      origin: "build",
    };
  }
  if (status === "skipped") {
    return {
      level: "info",
      message: summary || "Build skipped.",
      timestamp,
      origin: "build",
    };
  }
  return {
    level: "info",
    message: summary || `Build ${status}.`,
    timestamp,
    origin: "build",
  };
}

function formatRunCompletion(payload: Record<string, unknown>, timestamp: string): WorkbenchConsoleLine {
  const status = (payload.status as string | undefined) ?? "completed";
  const execution = (payload.execution as Record<string, unknown> | undefined) ?? {};
  const exit = typeof execution.exit_code === "number" ? execution.exit_code : undefined;
  const failure = payload.failure as Record<string, unknown> | undefined;
  const failureMessage = (failure?.message as string | undefined)?.trim();
  const summaryMessage = (payload.summary as string | undefined)?.trim();
  const level: WorkbenchConsoleLine["level"] =
    status === "failed"
      ? "error"
      : status === "canceled"
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

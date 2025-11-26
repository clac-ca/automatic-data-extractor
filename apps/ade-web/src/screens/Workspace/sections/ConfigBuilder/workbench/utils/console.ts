import { eventTimestamp, isAdeEvent } from "@shared/runs/types";
import type { AdeEvent as RunStreamEvent } from "@shared/runs/types";

import type { WorkbenchConsoleLine } from "../types";

const TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
};

export function formatConsoleTimestamp(value: number | Date | string): string {
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString([], TIME_OPTIONS);
}

export function describeBuildEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isAdeEvent(event)) {
    return { level: "info", message: JSON.stringify(event), timestamp: "" };
  }
  if (!event.type.startsWith("build.")) {
    return { level: "info", message: JSON.stringify(event), timestamp: formatConsoleTimestamp(eventTimestamp(event)) };
  }
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  switch (event.type) {
    case "build.created": {
      const reason = (event.reason as string | undefined) ?? (event.env?.reason as string | undefined) ?? "queued";
      return {
        level: "info",
        message: `Build ${event.build_id ?? ""} queued (${reason}).`,
        timestamp: ts,
      };
    }
    case "build.started":
      return { level: "info", message: "Build started.", timestamp: ts };
    case "build.phase.started": {
      const phase = (event.phase as string | undefined) ?? "building";
      const message = (event.message as string | undefined) ?? phase.replaceAll("_", " ");
      return { level: "info", message, timestamp: ts };
    }
    case "build.console":
      return formatConsole(event, ts);
    case "build.completed":
      return formatBuildCompletion(event, ts);
    default:
      return { level: "info", message: JSON.stringify(event), timestamp: ts };
  }
}

export function describeRunEvent(event: RunStreamEvent): WorkbenchConsoleLine {
  if (!isAdeEvent(event)) {
    return { level: "info", message: JSON.stringify(event), timestamp: "" };
  }
  const ts = formatConsoleTimestamp(eventTimestamp(event));
  const { type } = event;
  if (!type.startsWith("run.")) {
    return { level: "info", message: JSON.stringify(event), timestamp: ts };
  }

  switch (type) {
    case "run.queued":
      return {
        level: "info",
        message: `Run ${event.run_id ?? ""} queued${event.mode ? ` (${event.mode})` : ""}.`,
        timestamp: ts,
      };
    case "run.started":
      return {
        level: "info",
        message: `Run started${event.mode ? ` (${event.mode})` : ""}.`,
        timestamp: ts,
      };
    case "run.phase.started": {
      const phase = (event.phase as string | undefined) ?? "progress";
      return {
        level: "info",
        message: `Phase: ${phase}`,
        timestamp: ts,
      };
    }
    case "run.table.summary": {
      const name =
        (event.source_sheet as string | undefined) ??
        (event.source_file as string | undefined) ??
        (event.table_id as string | undefined) ??
        "table";
      return {
        level: "info",
        message: `Table completed (${name})`,
        timestamp: ts,
      };
    }
    case "run.validation.issue": {
      const sev = (event.severity as string | undefined) ?? "info";
      return {
        level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
        message: `Validation issue${event.code ? `: ${event.code as string}` : ""}`,
        timestamp: ts,
      };
    }
    case "run.console":
      return formatConsole(event, ts);
    case "run.completed":
      return formatRunCompletion(event, ts);
    default:
      return { level: "info", message: JSON.stringify(event), timestamp: ts };
  }
}

function formatConsole(event: RunStreamEvent, timestamp: string): WorkbenchConsoleLine {
  const stream = event.stream as string | undefined;
  const level = (event.level as string | undefined) ?? (stream === "stderr" ? "warning" : "info");
  return {
    level: normalizeLevel(level),
    message: String((event.message as string | undefined) ?? ""),
    timestamp,
  };
}

function formatBuildCompletion(event: RunStreamEvent, timestamp: string): WorkbenchConsoleLine {
  const status = (event.status as string | undefined) ?? (event.env?.status as string | undefined);
  const summary = (event.summary as string | undefined)?.trim();
  const exitCode = typeof event.exit_code === "number" ? event.exit_code : (event.execution as any)?.exit_code;
  if (status === "active") {
    return {
      level: "success",
      message: summary || "Build completed successfully.",
      timestamp,
    };
  }
  if (status === "canceled") {
    return { level: "warning", message: "Build was canceled before completion.", timestamp };
  }
  if (status === "failed") {
    const error = (event.error as Record<string, unknown> | undefined)?.message as string | undefined;
    const exit = typeof exitCode === "number" ? ` (exit code ${exitCode})` : "";
    return {
      level: "error",
      message: (error || summary || "Build failed.") + exit,
      timestamp,
    };
  }
  return {
    level: "info",
    message: summary || `Build ${status ?? "completed"}.`,
    timestamp,
  };
}

function formatRunCompletion(event: RunStreamEvent, timestamp: string): WorkbenchConsoleLine {
  const status = (event.status as string | undefined) ?? "completed";
  const execution = (event.execution as Record<string, unknown> | undefined) ?? {};
  const exit = typeof execution.exit_code === "number" ? execution.exit_code : undefined;
  const error = (event.error as Record<string, unknown> | undefined)?.message as string | undefined;
  const level: WorkbenchConsoleLine["level"] = normalizeLevel(
    status === "failed" ? "error" : status === "canceled" ? "warning" : status === "succeeded" ? "success" : undefined,
  );
  const exitPart = typeof exit === "number" ? ` (exit code ${exit})` : "";
  const base = error || `Run ${status}`;
  return {
    level,
    message: `${base}${exitPart}.`,
    timestamp,
  };
}

function normalizeLevel(level?: string): WorkbenchConsoleLine["level"] {
  if (level === "error") return "error";
  if (level === "warning" || level === "warn") return "warning";
  if (level === "success") return "success";
  return "info";
}

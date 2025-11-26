import type { BuildStatus } from "@shared/builds/types";
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
    case "build.created":
      return {
        level: "info",
        message: `Build ${event.build_id ?? ""} created (status: ${buildStatus(event) ?? "queued"}).`,
        timestamp: ts,
      };
    case "build.plan": {
      const reason = event.env?.reason ?? event.env?.plan_reason;
      const shouldBuild = event.env?.should_build === true;
      return {
        level: "info",
        message: shouldBuild ? `Planned rebuild (${reason ?? "pending"})` : `Env reuse (${reason ?? "reuse"})`,
        timestamp: ts,
      };
    }
    case "build.progress":
      return formatBuildProgress(event);
    case "build.log.delta":
      return formatBuildLog(event);
    case "build.completed":
      return formatBuildCompletion(event);
    default:
      return {
        level: "info",
        message: JSON.stringify(event),
        timestamp: ts,
      };
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
    case "run.created":
      return {
        level: "info",
        message: `Run ${event.run_id ?? ""} created.`,
        timestamp: ts,
      };
    case "run.started":
      return {
        level: "info",
        message: "Run started.",
        timestamp: ts,
      };
    case "run.pipeline.progress": {
      const phase = event.run?.phase ?? "progress";
      return {
        level: "info",
        message: `Phase: ${phase}`,
        timestamp: ts,
      };
    }
    case "run.table.summary": {
      const table = event.output_delta?.table as Record<string, unknown> | undefined;
      const name = table?.source_sheet ?? table?.source_file ?? "table";
      return {
        level: "info",
        message: `Table completed (${name})`,
        timestamp: ts,
      };
    }
    case "run.validation.issue.delta": {
      const sev = (event.validation?.severity as string) ?? "info";
      return {
        level: sev === "error" ? "error" : sev === "warning" ? "warning" : "info",
        message: `Validation issue${event.validation?.code ? `: ${event.validation.code}` : ""}`,
        timestamp: ts,
      };
    }
    case "run.log.delta":
      return formatRunLog(event);
    case "run.note":
      return {
        level: ((event.run?.level as string) ?? "info") as WorkbenchConsoleLine["level"],
        message: String(event.run?.message ?? "Note"),
        timestamp: ts,
      };
    case "run.completed": {
      const status = (event.run?.status as string) ?? (event.run?.engine_status as string) ?? "completed";
      const exit = event.run?.execution_summary?.exit_code as number | undefined;
      const level = status === "failed" ? "error" : status === "canceled" ? "warning" : "success";
      const exitPart = typeof exit === "number" ? ` (exit code ${exit})` : "";
      return {
        level,
        message: `Run ${status}${exitPart}.`,
        timestamp: ts,
      };
    }
    default:
      return {
        level: "info",
        message: JSON.stringify(event),
        timestamp: ts,
      };
  }
}

function buildStatus(event: RunStreamEvent): BuildStatus | undefined {
  const buildPayload = event.build;
  const envPayload = event.env;
  return (buildPayload?.status as BuildStatus | undefined) ?? (envPayload?.status as BuildStatus | undefined);
}

function formatBuildProgress(event: RunStreamEvent): WorkbenchConsoleLine {
  const phase = (event.build?.phase as string) ?? "building";
  const message = event.build?.message as string | undefined;
  return {
    level: "info",
    message: message?.trim() ? message : phase.replaceAll("_", " "),
    timestamp: formatConsoleTimestamp(eventTimestamp(event)),
  };
}

function formatBuildLog(event: RunStreamEvent): WorkbenchConsoleLine {
  const log = event.log ?? {};
  return {
    level: log.stream === "stderr" ? "warning" : "info",
    message: String(log.message ?? ""),
    timestamp: formatConsoleTimestamp(eventTimestamp(event)),
  };
}

function formatBuildCompletion(event: RunStreamEvent): WorkbenchConsoleLine {
  const timestamp = formatConsoleTimestamp(eventTimestamp(event));
  const status = buildStatus(event);
  if (status === "active") {
    return {
      level: "success",
      message: (event.build?.summary as string | undefined)?.trim() || "Build completed successfully.",
      timestamp,
    };
  }
  if (status === "canceled") {
    return {
      level: "warning",
      message: "Build was canceled before completion.",
      timestamp,
    };
  }
  const error =
    (event.build?.error_message as string | undefined)?.trim() ||
    (event.error?.message as string | undefined)?.trim() ||
    "Build failed.";
  const exit = typeof event.build?.exit_code === "number" ? ` (exit code ${event.build.exit_code})` : "";
  return {
    level: "error",
    message: `${error}${exit}`,
    timestamp,
  };
}

function formatRunLog(event: RunStreamEvent): WorkbenchConsoleLine {
  const log = event.log ?? {};
  return {
    level: log.stream === "stderr" ? "warning" : "info",
    message: String(log.message ?? ""),
    timestamp: formatConsoleTimestamp(eventTimestamp(event)),
  };
}

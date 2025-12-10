import { eventName, eventPayload, eventTimestamp, isEventRecord } from "@shared/runs/types";
import type { RunStreamEvent } from "@shared/runs/types";

import type { WorkbenchConsoleLine } from "../../types";

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

export function payloadOf(event: RunStreamEvent): Record<string, unknown> {
  return eventPayload(event);
}

export function normalizeLevel(level?: string): WorkbenchConsoleLine["level"] {
  if (level === "error") return "error";
  if (level === "warning" || level === "warn") return "warning";
  if (level === "success") return "success";
  return "info";
}

export function formatDurationMs(value?: unknown): string | null {
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

export function formatConsole(
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

export function isConsoleLine(event: RunStreamEvent): boolean {
  return eventName(event) === "console.line";
}

export function isBuildEvent(event: RunStreamEvent): boolean {
  if (!isEventRecord(event)) return false;
  const payload = payloadOf(event);
  return (
    (eventName(event).startsWith("build.")) ||
    (eventName(event) === "console.line" && (payload.scope as string | undefined) === "build")
  );
}

export function timestampLabel(event: RunStreamEvent): string {
  return formatConsoleTimestamp(eventTimestamp(event));
}

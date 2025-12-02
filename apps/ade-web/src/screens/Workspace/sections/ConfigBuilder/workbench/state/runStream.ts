import { describeBuildEvent, describeRunEvent } from "../utils/console";
import type { WorkbenchConsoleLine } from "../types";

import type { AdeEvent as RunStreamEvent } from "@shared/runs/types";

export type PhaseStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";

export type RunStreamStatus =
  | "idle"
  | "queued"
  | "waiting_for_build"
  | "building"
  | "running"
  | "succeeded"
  | "failed"
  | "canceled";

export type PhaseState = {
  readonly status: PhaseStatus;
  readonly durationMs?: number;
  readonly message?: string;
};

export interface RunStreamState {
  readonly runId: string | null;
  readonly runMode?: "validation" | "extraction";
  readonly status: RunStreamStatus;
  readonly buildPhases: Record<string, PhaseState>;
  readonly runPhases: Record<string, PhaseState>;
  readonly consoleLines: WorkbenchConsoleLine[];
  readonly tableSummaries: Record<string, unknown>;
  readonly validationSummary: Record<string, unknown> | null;
  readonly completedPayload: Record<string, unknown> | null;
  readonly lastSequence: number;
  readonly maxConsoleLines: number;
}

export type RunStreamAction =
  | { type: "RESET"; runId?: string | null; initialLines?: WorkbenchConsoleLine[] }
  | { type: "ATTACH_RUN"; runId: string | null; runMode?: "validation" | "extraction" }
  | { type: "CLEAR_CONSOLE" }
  | { type: "APPEND_LINE"; line: WorkbenchConsoleLine }
  | { type: "EVENT"; event: RunStreamEvent };

export function createRunStreamState(
  maxConsoleLines: number,
  initialLines?: readonly WorkbenchConsoleLine[],
): RunStreamState {
  return {
    runId: null,
    runMode: undefined,
    status: "idle",
    buildPhases: {},
    runPhases: {},
    consoleLines: clampConsoleLines(initialLines ?? [], maxConsoleLines),
    tableSummaries: {},
    validationSummary: null,
    completedPayload: null,
    lastSequence: 0,
    maxConsoleLines,
  };
}

export function runStreamReducer(state: RunStreamState, action: RunStreamAction): RunStreamState {
  switch (action.type) {
    case "RESET": {
      return {
        ...createRunStreamState(state.maxConsoleLines, action.initialLines),
        runId: action.runId ?? null,
      };
    }
    case "ATTACH_RUN":
      return {
        ...state,
        runId: action.runId,
        runMode: action.runMode ?? state.runMode,
      };
    case "CLEAR_CONSOLE":
      return { ...state, consoleLines: [] };
    case "APPEND_LINE": {
      const consoleLines = clampConsoleLines([...state.consoleLines, action.line], state.maxConsoleLines);
      return { ...state, consoleLines };
    }
    case "EVENT":
      return applyEventToState(state, action.event);
    default:
      return state;
  }
}

function applyEventToState(state: RunStreamState, event: RunStreamEvent): RunStreamState {
  const payload = extractPayload(event);
  const type = typeof event.type === "string" ? event.type : "";
  const sequence =
    typeof event.sequence === "number" && Number.isFinite(event.sequence)
      ? event.sequence
      : state.lastSequence;

  const isBuildEvent =
    type.startsWith("build.") || (type === "console.line" && (payload.scope as string | undefined) === "build");

  const line = isBuildEvent ? describeBuildEvent(event) : describeRunEvent(event);
  const consoleLines = clampConsoleLines([...state.consoleLines, line], state.maxConsoleLines);

  const buildPhases: Record<string, PhaseState> =
    type === "build.phase.started"
      ? {
          ...state.buildPhases,
          [payload.phase as string]: { status: "running", message: payload.message as string | undefined },
        }
      : type === "build.phase.completed"
        ? {
            ...state.buildPhases,
            [payload.phase as string]: {
              status: normalizePhaseStatus(payload.status),
              durationMs: asNumber(payload.duration_ms),
              message: payload.message as string | undefined,
            },
          }
        : state.buildPhases;

  const runPhases: Record<string, PhaseState> =
    type === "run.phase.started"
      ? {
          ...state.runPhases,
          [payload.phase as string]: { status: "running", message: payload.message as string | undefined },
        }
      : type === "run.phase.completed"
        ? {
            ...state.runPhases,
            [payload.phase as string]: {
              status: normalizePhaseStatus(payload.status),
              durationMs: asNumber(payload.duration_ms),
              message: payload.message as string | undefined,
            },
          }
        : state.runPhases;

  const validationSummary =
    type === "run.validation.summary" ? (payload as Record<string, unknown>) : state.validationSummary;

  const tableSummaries =
    type === "run.table.summary" && typeof payload.table_id === "string"
      ? { ...state.tableSummaries, [payload.table_id]: payload }
      : state.tableSummaries;

  const completedPayload =
    type === "run.completed" ? (payload as Record<string, unknown>) : state.completedPayload;

  const status = resolveStatus(state.status, type, payload);
  const runId = state.runId ?? (typeof event.run_id === "string" ? event.run_id : null);
  const runMode =
    typeof payload.mode === "string"
      ? payload.mode === "validation"
        ? "validation"
        : "extraction"
      : state.runMode;

  return {
    ...state,
    status,
    runId,
    runMode,
    buildPhases,
    runPhases,
    consoleLines,
    tableSummaries,
    validationSummary,
    completedPayload,
    lastSequence: Math.max(state.lastSequence, sequence),
  };
}

function resolveStatus(current: RunStreamStatus, type: string, payload: Record<string, unknown>): RunStreamStatus {
  switch (type) {
    case "run.queued":
      return "queued";
    case "run.waiting_for_build":
      return "waiting_for_build";
    case "build.started":
      return "building";
    case "run.started":
      return "running";
    case "run.error":
      return current === "failed" ? current : "failed";
    case "run.completed":
      return normalizeRunStatus(payload.status);
    default:
      return current;
  }
}

function normalizeRunStatus(value: unknown): RunStreamStatus {
  if (value === "succeeded") return "succeeded";
  if (value === "failed") return "failed";
  if (value === "canceled" || value === "cancelled") return "canceled";
  if (value === "waiting_for_build") return "waiting_for_build";
  return "running";
}

function normalizePhaseStatus(value: unknown): PhaseStatus {
  if (value === "failed") return "failed";
  if (value === "skipped") return "skipped";
  if (value === "succeeded") return "succeeded";
  if (value === "running") return "running";
  return "pending";
}

function extractPayload(event: RunStreamEvent): Record<string, unknown> {
  const payload = event?.payload;
  if (payload && typeof payload === "object") {
    return payload as Record<string, unknown>;
  }
  return {};
}

function clampConsoleLines(
  lines: readonly WorkbenchConsoleLine[],
  maxConsoleLines: number,
): WorkbenchConsoleLine[] {
  if (lines.length <= maxConsoleLines) {
    return lines.slice();
  }
  return lines.slice(lines.length - maxConsoleLines);
}

function asNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return undefined;
  }
  return value;
}

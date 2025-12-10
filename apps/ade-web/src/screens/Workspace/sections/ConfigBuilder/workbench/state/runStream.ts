import { formatConsoleEvent } from "../events/format";
import type {
  WorkbenchConsoleLine,
  WorkbenchValidationMessage,
  WorkbenchValidationState,
} from "../types";

import type { RunStreamEvent } from "@shared/runs/types";
import type { RunStatus } from "@shared/runs/types";

export type PhaseStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";

export type RunStreamStatus =
  | "idle"
  | "queued"
  | "waiting_for_build"
  | "building"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type PhaseState = {
  readonly status: PhaseStatus;
  readonly durationMs?: number;
  readonly message?: string;
};

export interface ValidationIssue {
  readonly level: "info" | "warning" | "error";
  readonly message: string;
  readonly path?: string;
  readonly code?: string;
}

export interface ValidationSummary {
  readonly issues?: ValidationIssue[];
  readonly issues_total?: number;
  readonly max_severity?: ValidationIssue["level"];
  readonly content_digest?: string | null;
  readonly error?: string | null;
}

export interface RunStreamState {
  readonly runId: string | null;
  readonly runMode?: "validation" | "extraction";
  readonly status: RunStreamStatus;
  readonly buildPhases: Record<string, PhaseState>;
  readonly runPhases: Record<string, PhaseState>;
  readonly consoleLines: WorkbenchConsoleLine[];
  readonly validationSummary: ValidationSummary | null;
  readonly completedPayload: Record<string, unknown> | null;
  readonly maxConsoleLines: number;
}

export type RunStreamAction =
  | {
      type: "RESET";
      runId?: string | null;
      initialLines?: WorkbenchConsoleLine[];
    }
  | { type: "ATTACH_RUN"; runId: string | null; runMode?: "validation" | "extraction" }
  | { type: "CLEAR_CONSOLE" }
  | { type: "APPEND_LINE"; line: WorkbenchConsoleLine }
  | { type: "EVENT"; event: RunStreamEvent };

export function createRunStreamState(
  maxConsoleLines: number,
  initialLines?: readonly WorkbenchConsoleLine[],
): RunStreamState {
  const seededLines = assignLineIds(clampConsoleLines(initialLines ?? [], maxConsoleLines), "initial");
  return {
    runId: null,
    runMode: undefined,
    status: "idle",
    buildPhases: {},
    runPhases: {},
    consoleLines: seededLines,
    validationSummary: null,
    completedPayload: null,
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
      const consoleLines = clampConsoleLines(
        [...state.consoleLines, withLineId(action.line, state.consoleLines.length)],
        state.maxConsoleLines,
      );
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
  const type = typeof event.event === "string" ? event.event : "";
  const eventMessage = typeof event.message === "string" ? event.message : undefined;

  const line = formatConsoleEvent(event);
  const consoleLines = clampConsoleLines(
    [...state.consoleLines, withLineId(line, state.consoleLines.length)],
    state.maxConsoleLines,
  );

  const buildPhases: Record<string, PhaseState> =
    type === "build.phase.started" || type === "build.phase.start"
      ? {
          ...state.buildPhases,
          [payload.phase as string]: { status: "running", message: eventMessage },
        }
      : type === "build.phase.completed" || type === "build.phase.complete"
        ? {
            ...state.buildPhases,
            [payload.phase as string]: {
              status: normalizePhaseStatus(payload.status),
              durationMs: asNumber(payload.duration_ms),
              message: eventMessage,
            },
          }
        : state.buildPhases;

  const runPhases: Record<string, PhaseState> =
    type === "run.phase.started" || type === "run.phase.start" || type === "engine.phase.start"
      ? {
          ...state.runPhases,
          [payload.phase as string]: { status: "running", message: eventMessage },
        }
      : type === "run.phase.completed" || type === "run.phase.complete" || type === "engine.phase.complete"
        ? {
            ...state.runPhases,
            [payload.phase as string]: {
              status: normalizePhaseStatus(payload.status),
              durationMs: asNumber(payload.duration_ms),
              message: eventMessage,
            },
          }
        : state.runPhases;

  let validationSummary: ValidationSummary | null = state.validationSummary;
  if (type === "run.validation.issue" || type === "engine.validation.issue") {
    const issue = toValidationIssue(payload, eventMessage);
    const existingIssues = validationSummary?.issues ?? [];
    validationSummary = {
      ...validationSummary,
      issues: issue ? [...existingIssues, issue] : existingIssues,
    };
  } else if (type === "run.validation.summary" || type === "engine.validation.summary") {
    validationSummary = normalizeValidationSummary(payload, validationSummary);
  }

  const completedPayload =
    type === "run.complete"
      ? (payload as Record<string, unknown>)
      : type === "engine.run.summary"
        ? (payload as Record<string, unknown>)
        : state.completedPayload;

  const status = resolveStatus(state.status, type, payload);
  const data = (event.data ?? {}) as Record<string, unknown>;
  const runId =
    state.runId ??
    (typeof data.jobId === "string"
      ? data.jobId
      : typeof data.run_id === "string"
        ? data.run_id
        : null);
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
    validationSummary,
    completedPayload,
  };
}

function resolveStatus(current: RunStreamStatus, type: string, payload: Record<string, unknown>): RunStreamStatus {
  switch (type) {
    case "run.queued":
      return "queued";
    case "run.waiting_for_build":
      return "waiting_for_build";
    case "build.started":
    case "build.start":
      return "building";
    case "run.start":
    case "run.started":
    case "engine.start":
      return "running";
    case "run.error":
      return current === "failed" ? current : "failed";
    case "engine.run.summary": {
      const source = (payload.source as Record<string, unknown> | undefined) ?? {};
      const sourceStatus = typeof source.status === "string" ? source.status : undefined;
      return normalizeRunStatusFromPayload(sourceStatus);
    }
    case "engine.complete":
      return normalizeRunStatusFromPayload((payload.status as string | undefined) ?? (payload.engine_status as string));
    case "run.complete":
      return normalizeRunStatusFromPayload(payload.status);
    default:
      return current;
  }
}

export function normalizeRunStatusValue(value?: RunStatus | RunStreamStatus | null): RunStreamStatus {
  if (value === "queued") return "queued";
  if (value === "waiting_for_build") return "waiting_for_build";
  if (value === "cancelled") return "cancelled";
  if (value === "building") return "building";
  if (value === "running") return "running";
  if (value === "succeeded") return "succeeded";
  if (value === "failed") return "failed";
  return "idle";
}

export function isRunStatusInProgress(status?: RunStatus | RunStreamStatus | null): boolean {
  const normalized = normalizeRunStatusValue(status);
  return (
    normalized === "queued" ||
    normalized === "waiting_for_build" ||
    normalized === "building" ||
    normalized === "running"
  );
}

export function isRunStatusTerminal(status?: RunStatus | RunStreamStatus | null): boolean {
  const normalized = normalizeRunStatusValue(status);
  return normalized === "succeeded" || normalized === "failed" || normalized === "cancelled";
}

function normalizeRunStatusFromPayload(value: unknown): RunStreamStatus {
  if (value === "succeeded") return "succeeded";
  if (value === "failed") return "failed";
  if (value === "cancelled") return "cancelled";
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
  const payload = event?.data;
  if (payload && typeof payload === "object") {
    return payload as Record<string, unknown>;
  }
  return {};
}

function toValidationIssue(payload: Record<string, unknown>, eventMessage?: string): ValidationIssue | null {
  const severity = (payload.severity as string | undefined) ?? (payload.level as string | undefined);
  const level: ValidationIssue["level"] =
    severity === "error" ? "error" : severity === "warning" ? "warning" : "info";
  const message =
    (eventMessage as string | undefined) ??
    (payload.code as string | undefined) ??
    "Validation issue";
  const path = payload.path as string | undefined;
  const code = payload.code as string | undefined;
  return { level, message, path, code };
}

function normalizeValidationSummary(
  payload: Record<string, unknown>,
  current?: ValidationSummary | null,
): ValidationSummary {
  const next: ValidationSummary = { ...(current ?? {}) };
  const rawIssues = payload.issues;
  if (Array.isArray(rawIssues)) {
    const issues = rawIssues
      .map((issue) =>
        issue && typeof issue === "object"
          ? toValidationIssue(issue as Record<string, unknown>)
          : null,
      )
      .filter(Boolean) as ValidationIssue[];
    next.issues = issues;
  }

  if ("issues_total" in payload) {
    const total = asNumber(payload.issues_total);
    if (typeof total === "number") {
      next.issues_total = total;
    }
  }

  if ("max_severity" in payload) {
    const severity = normalizeValidationSeverity(payload.max_severity);
    if (severity) {
      next.max_severity = severity;
    }
  }

  if ("content_digest" in payload) {
    const contentDigest = typeof payload.content_digest === "string" ? payload.content_digest : null;
    if (contentDigest !== undefined) {
      next.content_digest = contentDigest;
    }
  }

  if ("error" in payload) {
    const error = typeof payload.error === "string" ? payload.error : null;
    next.error = error;
  }

  return next;
}

export function deriveValidationStateFromStream(
  runStream: RunStreamState,
  seedValidation?: readonly WorkbenchValidationMessage[],
): WorkbenchValidationState {
  const summary: ValidationSummary | null =
    runStream.validationSummary ?? (seedValidation ? { issues: seedValidation } : null);
  const mode = runStream.runMode ?? (summary ? "validation" : undefined);
  if (!mode && !summary) {
    return { status: "idle", messages: [], lastRunAt: undefined, error: null, digest: null };
  }

  const status = normalizeRunStatusValue(runStream.status);
  const inProgress = isRunStatusInProgress(status);
  const issues = summary?.issues ?? [];
  const hasError = Boolean(summary?.error);
  const lastRunAt =
    (typeof runStream.completedPayload?.completed_at === "string" && runStream.completedPayload.completed_at) || undefined;

  let derivedStatus: WorkbenchValidationState["status"];
  if (inProgress && mode === "validation") {
    derivedStatus = "running";
  } else if (hasError || status === "failed" || status === "cancelled") {
    derivedStatus = "error";
  } else if (issues.length > 0 || status === "succeeded") {
    derivedStatus = "success";
  } else {
    derivedStatus = "idle";
  }

  const error =
    derivedStatus === "error"
      ? summary?.error ?? "Validation failed."
      : null;

  return {
    status: derivedStatus,
    messages: issues,
    lastRunAt: lastRunAt ?? undefined,
    error,
    digest: summary?.content_digest ?? null,
  };
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

function assignLineIds(
  lines: readonly WorkbenchConsoleLine[],
  seed: string,
): WorkbenchConsoleLine[] {
  return lines.map((line, index) => withLineId(line, index, seed));
}

function withLineId(
  line: WorkbenchConsoleLine,
  index: number,
  seed = "line",
): WorkbenchConsoleLine {
  if (line.id) return line;
  const random =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : Math.random().toString(16).slice(2);
  const origin = line.origin ?? "run";
  const timestamp = line.timestamp ?? "ts";
  return {
    ...line,
    id: `${seed}-${origin}-${timestamp}-${index}-${random}`,
  };
}

function asNumber(value: unknown): number | undefined {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return undefined;
  }
  return value;
}

function normalizeValidationSeverity(value: unknown): ValidationIssue["level"] | undefined {
  if (value === "error") return "error";
  if (value === "warning") return "warning";
  if (value === "info") return "info";
  return undefined;
}

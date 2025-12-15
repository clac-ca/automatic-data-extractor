import type {
  WorkbenchValidationMessage,
  WorkbenchValidationState,
} from "../types";

import { eventName, eventPayload, type RunStatus, type RunStreamEvent } from "@shared/runs/types";

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
  readonly issues?: readonly ValidationIssue[];
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
  readonly validationSummary: ValidationSummary | null;
  readonly completedPayload: Record<string, unknown> | null;
}

export type RunStreamAction =
  | {
      type: "RESET";
      runId?: string | null;
    }
  | { type: "ATTACH_RUN"; runId: string | null; runMode?: "validation" | "extraction" }
  | { type: "EVENTS"; events: RunStreamEvent[] };

export function createRunStreamState(
): RunStreamState {
  return {
    runId: null,
    runMode: undefined,
    status: "idle",
    buildPhases: {},
    runPhases: {},
    validationSummary: null,
    completedPayload: null,
  };
}

export function runStreamReducer(state: RunStreamState, action: RunStreamAction): RunStreamState {
  switch (action.type) {
    case "RESET": {
      return {
        ...createRunStreamState(),
        runId: action.runId ?? null,
      };
    }
    case "ATTACH_RUN":
      return {
        ...state,
        runId: action.runId,
        runMode: action.runMode ?? state.runMode,
      };
    case "EVENTS": {
      let next = state;
      for (const event of action.events) {
        next = applyEventToState(next, event);
      }
      return next;
    }
    default:
      return state;
  }
}

function applyEventToState(state: RunStreamState, event: RunStreamEvent): RunStreamState {
  const payload = eventPayload(event);
  const type = eventName(event);
  const eventMessage = typeof event.message === "string" ? event.message : undefined;

  let buildPhases = state.buildPhases;
  const buildPhaseKey = typeof payload.phase === "string" ? payload.phase : null;
  if (buildPhaseKey) {
    if (type === "build.phase.started" || type === "build.phase.start") {
      buildPhases = {
        ...buildPhases,
        [buildPhaseKey]: { status: "running", message: eventMessage },
      };
    } else if (type === "build.phase.completed" || type === "build.phase.complete") {
      buildPhases = {
        ...buildPhases,
        [buildPhaseKey]: {
          status: normalizePhaseStatus(payload.status),
          durationMs: asNumber(payload.duration_ms),
          message: eventMessage,
        },
      };
    }
  }

  let runPhases = state.runPhases;
  const runPhaseKey = typeof payload.phase === "string" ? payload.phase : null;
  if (runPhaseKey) {
    if (type === "run.phase.started" || type === "run.phase.start" || type === "engine.phase.start") {
      runPhases = {
        ...runPhases,
        [runPhaseKey]: { status: "running", message: eventMessage },
      };
    } else if (type === "run.phase.completed" || type === "run.phase.complete" || type === "engine.phase.complete") {
      runPhases = {
        ...runPhases,
        [runPhaseKey]: {
          status: normalizePhaseStatus(payload.status),
          durationMs: asNumber(payload.duration_ms),
          message: eventMessage,
        },
      };
    }
  }

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
  const runId =
    state.runId ??
    (typeof payload.jobId === "string"
      ? payload.jobId
      : typeof payload.run_id === "string"
        ? payload.run_id
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

export function isRunStatusTerminal(
  status?: RunStatus | RunStreamStatus | null,
): status is Extract<RunStatus | RunStreamStatus, "succeeded" | "failed" | "cancelled"> {
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
  const base = current ?? {};

  const rawIssues = payload.issues;
  const issues = Array.isArray(rawIssues)
    ? (rawIssues
        .map((issue) =>
          issue && typeof issue === "object"
            ? toValidationIssue(issue as Record<string, unknown>)
            : null,
        )
        .filter(Boolean) as ValidationIssue[])
    : base.issues;

  const total = "issues_total" in payload ? asNumber(payload.issues_total) : base.issues_total;
  const maxSeverity = "max_severity" in payload ? normalizeValidationSeverity(payload.max_severity) : base.max_severity;
  const contentDigest =
    "content_digest" in payload
      ? typeof payload.content_digest === "string"
        ? payload.content_digest
        : null
      : base.content_digest;
  const error = "error" in payload ? (typeof payload.error === "string" ? payload.error : null) : base.error;

  return {
    ...base,
    issues,
    issues_total: total,
    max_severity: maxSeverity ?? undefined,
    content_digest: contentDigest,
    error,
  };
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

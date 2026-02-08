import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { WorkbenchConsoleStore } from "./consoleStore";
import type { WorkbenchConsoleLine } from "../types";

import {
  createRun,
  fetchRun,
  streamRunEventsForRun,
  type RunResource,
  type RunStreamConnectionState,
  type RunStreamOptions,
} from "@/api/runs/api";
import { eventName, eventPayload, eventTimestamp, type RunStreamEvent } from "@/types/runs";

export type JobStreamStatus = "idle" | "running" | "succeeded" | "failed";

export interface JobStreamMetadata {
  readonly mode: "validation" | "extraction" | "publish";
  readonly documentId?: string;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
}

type StartJobExtras = {
  readonly prepare?: () => boolean;
};

type UseJobStreamControllerOptions = {
  readonly workspaceId: string;
  readonly configId: string;
  readonly onJobIdChange?: (jobId: string | null) => void;
  readonly seed?: {
    readonly console?: readonly WorkbenchConsoleLine[];
  };
  readonly maxConsoleLines?: number;
  readonly onError?: (error: unknown) => void;
};

function coerceNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function resolveRunCompletionStatus(payload: Record<string, unknown>): JobStreamStatus {
  const statusRaw = typeof payload.status === "string" ? payload.status.toLowerCase() : "";
  if (statusRaw === "succeeded" || statusRaw === "success") {
    return "succeeded";
  }
  if (statusRaw === "failed" || statusRaw === "cancelled") {
    return "failed";
  }

  const exitCode = coerceNumber(payload.exit_code ?? payload.exitCode);
  if (typeof exitCode === "number") {
    return exitCode === 0 ? "succeeded" : "failed";
  }

  const timedOut =
    typeof payload.timed_out === "boolean"
      ? payload.timed_out
      : typeof payload.timedOut === "boolean"
        ? payload.timedOut
        : null;
  if (timedOut) {
    return "failed";
  }

  return "succeeded";
}

function resolveRunResourceStatus(status: RunResource["status"]): JobStreamStatus {
  if (status === "failed" || status === "cancelled") {
    return "failed";
  }
  if (status === "succeeded") {
    return "succeeded";
  }
  return "failed";
}

export function useJobStreamController({
  workspaceId,
  configId,
  onJobIdChange,
  seed,
  maxConsoleLines = 2000,
  onError,
}: UseJobStreamControllerOptions): {
  readonly console: WorkbenchConsoleStore;
  readonly jobId: string | null;
  readonly jobMode: JobStreamMetadata["mode"] | null;
  readonly jobConnectionState: RunStreamConnectionState | null;
  readonly jobStatus: JobStreamStatus;
  readonly jobInProgress: boolean;
  readonly completedDetails: Record<string, unknown> | null;
  readonly clearConsole: () => void;
  readonly startJob: (
    options: RunStreamOptions,
    metadata: JobStreamMetadata,
    extras?: StartJobExtras,
  ) => Promise<{ jobId: string; startedAt: string } | null>;
} {
  const consoleStoreRef = useRef<WorkbenchConsoleStore>(
    new WorkbenchConsoleStore(
      maxConsoleLines,
      seed?.console ? [...seed.console].slice(-maxConsoleLines) : undefined,
    ),
  );

  const controllerRef = useRef<AbortController | null>(null);
  const startInFlightRef = useRef(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [jobMode, setJobMode] = useState<JobStreamMetadata["mode"] | null>(null);
  const [jobConnectionState, setJobConnectionState] = useState<RunStreamConnectionState | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStreamStatus>("idle");
  const [completedDetails, setCompletedDetails] = useState<Record<string, unknown> | null>(null);

  const jobInProgress = jobStatus === "running";

  const stopStreaming = useCallback(() => {
    const controller = controllerRef.current;
    if (controller) {
      controller.abort();
      controllerRef.current = null;
    }
  }, []);

  useEffect(
    () => () => {
      stopStreaming();
    },
    [stopStreaming],
  );

  const clearConsole = useCallback(() => {
    consoleStoreRef.current.clear();
  }, []);

  const pushError = useCallback(
    (error: unknown) => {
      if (onError) onError(error);
    },
    [onError],
  );

  const pushEvent = useCallback(
    (evt: RunStreamEvent) => {
      const name = eventName(evt);

      const payload = eventPayload(evt);
      const scopeRaw =
        name.startsWith("environment.")
          ? "environment"
          : name === "console.line" && typeof payload.scope === "string"
            ? payload.scope
            : "run";
      const scope = scopeRaw.includes("environment") ? "environment" : "run";

      const levelRaw = typeof evt.level === "string" ? evt.level.toLowerCase() : "info";
      const level: WorkbenchConsoleLine["level"] =
        levelRaw === "debug" || levelRaw === "warning" || levelRaw === "error" || levelRaw === "success"
          ? (levelRaw as WorkbenchConsoleLine["level"])
          : "info";

      const msg = typeof evt.message === "string" ? evt.message : "";
      const message = msg.trim() ? msg : name;

      const line: WorkbenchConsoleLine = {
        id: typeof evt.event_id === "string" ? evt.event_id : undefined,
        level,
        message,
        timestamp: eventTimestamp(evt),
        origin: scope,
        raw: evt,
      };
      consoleStoreRef.current.append(line);

      if (name === "run.complete") {
        const resolvedStatus = resolveRunCompletionStatus(payload);
        setCompletedDetails({ ...payload, status: resolvedStatus });
        setJobStatus(resolvedStatus);
        setJobConnectionState("completed");
      }
    },
    [],
  );

  const startJob = useCallback(
    async (
      options: RunStreamOptions,
      metadata: JobStreamMetadata,
      extras?: StartJobExtras,
    ): Promise<{ jobId: string; startedAt: string } | null> => {
      if (startInFlightRef.current || jobInProgress) {
        return null;
      }
      if (extras?.prepare && extras.prepare() === false) {
        return null;
      }

      stopStreaming();
      clearConsole();
      setCompletedDetails(null);
      setJobMode(metadata.mode);
      setJobConnectionState("connecting");
      setJobStatus("running");
      setJobId(null);
      onJobIdChange?.(null);

      const startedAt = new Date().toISOString();
      const controller = new AbortController();
      controllerRef.current = controller;
      startInFlightRef.current = true;

      let resolvedJobId: string | null = null;
      try {
        const operation = options.operation ?? "process";
        const run = await createRun(
          workspaceId,
          { ...options, operation, configuration_id: configId },
          controller.signal,
        );
        resolvedJobId = run.id;
        setJobId(run.id);
        onJobIdChange?.(run.id);

        const operationLabel =
          operation === "publish" ? "Publish" : operation === "validate" ? "Validation" : "Test run";
        consoleStoreRef.current.append({
          level: "info",
          message: `${operationLabel} started · run ${run.id}`,
          timestamp: startedAt,
          origin: "run",
        });

        let observedCompletionEvent = false;
        for await (const evt of streamRunEventsForRun(workspaceId, run, {
          afterSequence: 0,
          signal: controller.signal,
          onConnectionStateChange: (state) => {
            if (!controller.signal.aborted) {
              setJobConnectionState(state);
            }
          },
        })) {
          pushEvent(evt);
          if (eventName(evt) === "run.complete") {
            observedCompletionEvent = true;
            break;
          }
        }

        if (!controller.signal.aborted && !observedCompletionEvent) {
          const terminalRun = await fetchRun(workspaceId, run.id, controller.signal);
          const resolvedStatus = resolveRunResourceStatus(terminalRun.status);
          setCompletedDetails({ status: resolvedStatus });
          setJobStatus(resolvedStatus);
          setJobConnectionState("completed");
        }

        if (!resolvedJobId) {
          throw new Error("Run creation response missing run id.");
        }
        return { jobId: resolvedJobId, startedAt };
      } catch (error) {
        if (!controller.signal.aborted) {
          setJobStatus("failed");
          setJobConnectionState("failed");
          pushError(error);
        }
        return null;
      } finally {
        startInFlightRef.current = false;
        if (controllerRef.current === controller) {
          controllerRef.current = null;
        }
      }
    },
    [clearConsole, configId, jobInProgress, onJobIdChange, pushError, pushEvent, stopStreaming, workspaceId],
  );

  return useMemo(
    () => ({
      console: consoleStoreRef.current,
      jobId,
      jobMode,
      jobConnectionState,
      jobStatus,
      jobInProgress,
      completedDetails,
      clearConsole,
      startJob,
    }),
    [jobId, jobMode, jobConnectionState, jobStatus, jobInProgress, completedDetails, clearConsole, startJob],
  );
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { WorkbenchConsoleStore } from "./consoleStore";
import type { WorkbenchConsoleLine } from "../types";

import { createRun, streamRunEventsForRun, type RunStreamOptions } from "@api/runs/api";
import { eventName, eventPayload, eventTimestamp, type RunStreamEvent } from "@schema/runs";

export type JobStreamStatus = "idle" | "running" | "succeeded" | "failed";

export interface JobStreamMetadata {
  readonly mode: "validation" | "extraction";
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
        setCompletedDetails(payload);
        const status = typeof payload.status === "string" ? payload.status.toLowerCase() : "";
        if (status === "succeeded" || status === "success") {
          setJobStatus("succeeded");
        } else {
          setJobStatus("failed");
        }
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
      setJobStatus("running");
      setJobId(null);
      onJobIdChange?.(null);

      const startedAt = new Date().toISOString();
      const controller = new AbortController();
      controllerRef.current = controller;
      startInFlightRef.current = true;

      let resolvedJobId: string | null = null;
      try {
        const run = await createRun(
          workspaceId,
          { ...options, configuration_id: configId },
          controller.signal,
        );
        resolvedJobId = run.id;
        setJobId(run.id);
        onJobIdChange?.(run.id);

        for await (const evt of streamRunEventsForRun(run, { afterSequence: 0, signal: controller.signal })) {
          pushEvent(evt);
          if (eventName(evt) === "run.complete") {
            break;
          }
        }

        if (!resolvedJobId) {
          throw new Error("Run creation response missing run id.");
        }
        return { jobId: resolvedJobId, startedAt };
      } catch (error) {
        if (!controller.signal.aborted) {
          setJobStatus("failed");
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
      jobStatus,
      jobInProgress,
      completedDetails,
      clearConsole,
      startJob,
    }),
    [jobId, jobMode, jobStatus, jobInProgress, completedDetails, clearConsole, startJob],
  );
}

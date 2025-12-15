import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { WorkbenchConsoleStore } from "./consoleStore";
import type { WorkbenchConsoleLine } from "../types";

import { streamConfigurationJob } from "@shared/jobs/api";
import type { RunStreamOptions } from "@shared/runs/api";

export type JobStreamStatus = "idle" | "running" | "succeeded" | "failed" | "cancelled";

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
  readonly configId: string;
  readonly onJobIdChange?: (jobId: string | null) => void;
  readonly seed?: {
    readonly console?: readonly WorkbenchConsoleLine[];
  };
  readonly maxConsoleLines?: number;
  readonly onError?: (error: unknown) => void;
};

export function useJobStreamController({
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
        for await (const msg of streamConfigurationJob(configId, options, controller.signal)) {
          if (msg.type === "meta") {
            const nextId = typeof msg.event.details?.jobId === "string" ? msg.event.details.jobId : null;
            if (nextId && !resolvedJobId) {
              resolvedJobId = nextId;
              setJobId(nextId);
              onJobIdChange?.(nextId);
            }
            continue;
          }

          if (msg.type === "log") {
            const line: WorkbenchConsoleLine = {
              level: msg.line.level,
              message: msg.line.message,
              timestamp: msg.line.ts,
              origin: msg.line.scope === "build" ? "build" : "run",
            };
            consoleStoreRef.current.append(line);
            continue;
          }

          if (msg.type === "done") {
            const details = msg.event.details ?? {};
            setCompletedDetails(details);
            const status = typeof details.status === "string" ? details.status.toLowerCase() : "";
            if (status === "succeeded" || status === "success") {
              setJobStatus("succeeded");
            } else if (status === "cancelled" || status === "canceled") {
              setJobStatus("cancelled");
            } else if (status) {
              setJobStatus("failed");
            } else {
              setJobStatus("failed");
            }
            break;
          }
        }

        if (!resolvedJobId) {
          throw new Error("Job stream ended before returning a job id.");
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
    [clearConsole, configId, jobInProgress, onJobIdChange, pushError, stopStreaming],
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


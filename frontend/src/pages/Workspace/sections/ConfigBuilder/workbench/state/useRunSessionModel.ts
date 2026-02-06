import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useJobStreamController, type JobStreamMetadata, type JobStreamStatus } from "./useJobStreamController";
import type { WorkbenchDataSeed, WorkbenchRunSummary, WorkbenchValidationState } from "../types";

import {
  fetchRun,
  runInputUrl,
  runLogsUrl,
  runOutputUrl,
  type RunStreamOptions,
} from "@/api/runs/api";
import type { RunStatus } from "@/types/runs";

export type RunCompletionInfo = {
  readonly runId: string;
  readonly status: RunStatus;
  readonly mode: "validation" | "extraction";
  readonly startedAt?: string | null;
  readonly completedAt?: string | null;
  readonly durationMs?: number | null;
  readonly payload?: Record<string, unknown> | null;
};

interface UseRunSessionModelOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly runId: string | null;
  readonly seed?: WorkbenchDataSeed;
  readonly maxConsoleLines?: number;
  readonly onRunIdChange?: (runId: string | null) => void;
  readonly onRunComplete?: (info: RunCompletionInfo) => void;
}

function isTerminal(status: JobStreamStatus) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

function normalizeRunStatus(value?: string | null): RunStatus {
  const normalized = (value ?? "").toLowerCase();
  if (normalized === "succeeded" || normalized === "failed" || normalized === "cancelled") {
    return normalized;
  }
  if (normalized === "success") return "succeeded";
  return "failed";
}

export function useRunSessionModel({
  workspaceId,
  configId,
  runId,
  seed,
  maxConsoleLines,
  onRunIdChange,
  onRunComplete,
}: UseRunSessionModelOptions) {
  const lastRunMetadataRef = useRef<JobStreamMetadata | null>(null);
  const {
    console,
    jobId,
    jobMode,
    jobStatus,
    jobInProgress,
    completedDetails,
    clearConsole,
    startJob,
  } = useJobStreamController({
    workspaceId,
    configId,
    onJobIdChange: onRunIdChange,
    seed: seed ? { console: seed.console } : undefined,
    maxConsoleLines,
  });

  const resolvedRunId = jobId ?? runId;
  const runMode = jobMode ?? null;

  const [latestRun, setLatestRun] = useState<WorkbenchRunSummary | null>(null);
  const lastCompletedRunRef = useRef<string | null>(null);

  const validation: WorkbenchValidationState = useMemo(
    () => ({
      status: jobInProgress && runMode === "validation" ? "running" : "idle",
      messages: [],
      lastRunAt: undefined,
      error: null,
      digest: null,
    }),
    [jobInProgress, runMode],
  );

  // When the job finishes, capture completion info and hydrate output/log links.
  useEffect(() => {
    if (!resolvedRunId || !isTerminal(jobStatus)) {
      return;
    }
    if (lastCompletedRunRef.current === resolvedRunId) {
      return;
    }
    lastCompletedRunRef.current = resolvedRunId;

    const status = normalizeRunStatus(typeof completedDetails?.status === "string" ? completedDetails.status : null);
    const mode: "validation" | "extraction" = runMode ?? "extraction";

    const execution = (completedDetails?.execution as Record<string, unknown> | undefined) ?? {};
    const startedAt = typeof execution.started_at === "string" ? execution.started_at : null;
    const completedAt = typeof execution.completed_at === "string" ? execution.completed_at : new Date().toISOString();
    const durationMs = typeof execution.duration_ms === "number" ? execution.duration_ms : null;

    onRunComplete?.({
      runId: resolvedRunId,
      status,
      mode,
      startedAt,
      completedAt,
      durationMs,
      payload: completedDetails,
    });

    if (mode === "validation") {
      return;
    }

    const runMetadata = lastRunMetadataRef.current;
    const artifacts = (completedDetails?.artifacts as Record<string, unknown> | undefined) ?? {};
    const outputPath = typeof artifacts.output_path === "string" ? artifacts.output_path : null;
    const processedFile = typeof artifacts.processed_file === "string" ? artifacts.processed_file : null;

    setLatestRun({
      runId: resolvedRunId,
      status,
      outputUrl: undefined,
      inputUrl: undefined,
      outputReady: outputPath ? true : undefined,
      outputFilename: outputPath ? basename(outputPath) : null,
      outputPath,
      logsUrl: undefined,
      processedFile,
      outputLoaded: false,
      documentName: runMetadata?.documentName,
      sheetNames: runMetadata?.sheetNames ?? [],
      error: null,
      startedAt,
      completedAt,
      durationMs,
    });

    void (async () => {
      try {
        const resource = await fetchRun(resolvedRunId);
        const outputUrl = runOutputUrl(resource) ?? undefined;
        const logsUrl = runLogsUrl(resource) ?? undefined;
        const inputUrl = runInputUrl(resource) ?? undefined;
        setLatestRun((prev) =>
          prev && prev.runId === resolvedRunId
            ? {
                ...prev,
                outputUrl: outputUrl ?? prev.outputUrl,
                outputReady: outputUrl ? true : prev.outputReady,
                logsUrl: logsUrl ?? prev.logsUrl,
                inputUrl: inputUrl ?? prev.inputUrl,
                outputLoaded: true,
              }
            : prev,
        );
      } catch {
        setLatestRun((prev) =>
          prev && prev.runId === resolvedRunId ? { ...prev, outputLoaded: true } : prev,
        );
      }
    })();
  }, [resolvedRunId, jobStatus, completedDetails, onRunComplete, runMode]);

  const startRun = useCallback(
    async (
      options: RunStreamOptions,
      metadata: JobStreamMetadata,
      extras?: { prepare?: () => boolean },
    ) => {
      lastRunMetadataRef.current = metadata;
      const result = await startJob(options, metadata, { prepare: extras?.prepare });
      if (result && metadata.mode === "extraction") {
        setLatestRun(null);
      }
      return result ? { runId: result.jobId, startedAt: result.startedAt } : null;
    },
    [startJob],
  );

  const runStatus: JobStreamStatus = jobStatus;

  return useMemo(
    () => ({
      runStatus,
      runMode: runMode ?? undefined,
      runInProgress: jobInProgress,
      validation,
      console,
      latestRun,
      clearConsole,
      startRun,
    }),
    [runStatus, runMode, jobInProgress, validation, console, latestRun, clearConsole, startRun],
  );
}

function basename(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return "";
  const parts = trimmed.split("/");
  return parts[parts.length - 1] || trimmed;
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { isRunStatusTerminal, normalizeRunStatusValue } from "./runStream";
import { useRunStreamController, type RunStreamMetadata } from "./useRunStreamController";
import type { WorkbenchDataSeed, WorkbenchRunSummary } from "../types";

import {
  fetchRun,
  runLogsUrl,
  runOutputUrl,
  type RunResource,
  type RunStreamOptions,
} from "@shared/runs/api";
import type { RunStatus } from "@shared/runs/types";

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
  readonly configId: string;
  readonly runId: string | null;
  readonly seed?: WorkbenchDataSeed;
  readonly maxConsoleLines?: number;
  readonly onRunIdChange?: (runId: string | null) => void;
  readonly onRunComplete?: (info: RunCompletionInfo) => void;
}

export function useRunSessionModel({
  configId,
  runId,
  seed,
  maxConsoleLines,
  onRunIdChange,
  onRunComplete,
}: UseRunSessionModelOptions) {
  const {
    stream,
    console,
    runResource,
    runMetadata,
    runStartedAt,
    runStatus,
    runMode,
    runInProgress,
    validation,
    appendConsoleLine,
    clearConsole,
    startRun,
  } = useRunStreamController({
    configId,
    runId,
    onRunIdChange,
    seed,
    maxConsoleLines,
  });

  const [latestRun, setLatestRun] = useState<WorkbenchRunSummary | null>(null);
  const lastCompletedRunRef = useRef<string | null>(null);

  // Fetch output/telemetry/summary exactly once when a run finishes.
  useEffect(() => {
    if (!runId || !isRunStatusTerminal(runStatus)) {
      return;
    }
    if (lastCompletedRunRef.current === runId) {
      return;
    }
    lastCompletedRunRef.current = runId;

    const completedPayload = stream.completedPayload ?? {};
    const failure = completedPayload.failure as Record<string, unknown> | undefined;
    const failureMessage = typeof failure?.message === "string" ? failure.message.trim() : null;
    const summaryMessage = typeof completedPayload.summary === "string" ? completedPayload.summary.trim() : null;
    const payloadStartedAt = typeof completedPayload.started_at === "string" ? completedPayload.started_at : undefined;
    const payloadSource = completedPayload.source as Record<string, unknown> | undefined;
    const payloadSourceStartedAt = typeof payloadSource?.started_at === "string" ? payloadSource.started_at : undefined;
    const payloadCompletedAt = typeof completedPayload.completed_at === "string" ? completedPayload.completed_at : undefined;
    const payloadSourceCompletedAt =
      typeof payloadSource?.completed_at === "string" ? payloadSource.completed_at : undefined;
    const payloadStatus =
      (completedPayload.status as RunStatus | undefined) ??
      (payloadSource?.status as RunStatus | undefined) ??
      runStatus;
    const completedDetails =
      completedPayload.details && typeof completedPayload.details === "object"
        ? (completedPayload.details as Record<string, unknown>)
        : null;
    const artifacts =
      completedPayload.artifacts && typeof completedPayload.artifacts === "object"
        ? (completedPayload.artifacts as Record<string, unknown>)
        : null;
    const artifactOutputPath = extractOutputPath(artifacts) ?? extractOutputPath(completedDetails);
    const artifactProcessedFile = extractProcessedFile(artifacts) ?? extractProcessedFile(completedDetails);

    const normalizedStatus = normalizeRunStatusValue(payloadStatus);
    const completionStatus: RunStatus =
      normalizedStatus === "succeeded" || normalizedStatus === "failed" || normalizedStatus === "cancelled"
        ? normalizedStatus
        : runStatus;
    const resolvedMode: "validation" | "extraction" = runMode ?? runMetadata?.mode ?? "extraction";
    const startedAtIso =
      payloadStartedAt ?? payloadSourceStartedAt ?? runResource?.started_at ?? runStartedAt ?? undefined;
    const completedIso =
      payloadCompletedAt ??
      payloadSourceCompletedAt ??
      runResource?.completed_at ??
      new Date().toISOString();
    const durationMs = calculateDurationMs(startedAtIso ?? null, completedIso ?? null);

    onRunComplete?.({
      runId,
      status: completionStatus,
      mode: resolvedMode,
      startedAt: startedAtIso ?? null,
      completedAt: completedIso ?? new Date().toISOString(),
      durationMs,
      payload: stream.completedPayload,
    });

    if (resolvedMode === "validation") {
      return;
    }

    setLatestRun((previous) => {
      const outputMeta = deriveOutputMetadata({
        runResource,
        fallbackPath: artifactOutputPath ?? previous?.outputPath ?? null,
        fallbackProcessedFile: artifactProcessedFile ?? previous?.processedFile ?? null,
      });
      const logsUrl = runResource ? runLogsUrl(runResource) ?? undefined : previous?.logsUrl;
      return {
        runId,
        status: completionStatus,
        outputUrl: outputMeta.outputUrl ?? previous?.outputUrl,
        outputPath: outputMeta.outputPath,
        outputFilename: outputMeta.outputFilename ?? previous?.outputFilename,
        outputReady: outputMeta.outputReady ?? previous?.outputReady ?? (outputMeta.outputPath ? true : undefined),
        processedFile: outputMeta.processedFile ?? previous?.processedFile ?? null,
        outputLoaded: true,
        logsUrl,
        documentName: runMetadata?.documentName ?? previous?.documentName,
        sheetNames: runMetadata?.sheetNames ?? previous?.sheetNames ?? [],
        summary: null,
        summaryLoaded: true,
        summaryError: null,
        telemetry: null,
        telemetryLoaded: true,
        telemetryError: null,
        error: failureMessage ?? summaryMessage ?? previous?.error ?? null,
        startedAt: startedAtIso ?? previous?.startedAt ?? null,
        completedAt: completedIso ?? previous?.completedAt ?? null,
        durationMs,
      };
    });

    void (async () => {
      let currentResource = runResource;
      if (!currentResource) {
        try {
          currentResource = await fetchRun(runId);
        } catch (error) {
          setLatestRun((previous) =>
            previous && previous.runId === runId
              ? { ...previous, outputLoaded: true, summaryLoaded: true, telemetryLoaded: true, error: describeError(error) }
              : previous,
          );
        }
      }

      if (currentResource) {
        const outputMeta = deriveOutputMetadata({
          runResource: currentResource,
          fallbackPath: artifactOutputPath ?? null,
          fallbackProcessedFile: artifactProcessedFile ?? null,
        });
        const logsUrl = runLogsUrl(currentResource) ?? undefined;
        setLatestRun((previous) =>
          previous && previous.runId === runId
            ? {
                ...previous,
                outputUrl: outputMeta.outputUrl ?? previous.outputUrl,
                outputPath: outputMeta.outputPath ?? previous.outputPath ?? null,
                outputFilename: outputMeta.outputFilename ?? previous.outputFilename,
                outputReady: outputMeta.outputReady ?? previous.outputReady,
                processedFile: outputMeta.processedFile ?? previous.processedFile,
                outputLoaded: true,
                logsUrl,
              }
            : previous,
        );
      }
    })();
  }, [runId, runStatus, runMode, runMetadata, runResource, runStartedAt, stream.completedPayload, onRunComplete]);

  const startManagedRun = useCallback(
    async (
      options: RunStreamOptions,
      metadata: RunStreamMetadata,
      extras?: { forceRebuild?: boolean; prepare?: () => boolean },
    ) => {
      const result = await startRun(options, metadata, extras);
      if (result && metadata.mode === "extraction") {
        setLatestRun(null);
      }
      return result;
    },
    [startRun],
  );

  return useMemo(
    () => ({
      stream,
      runStatus,
      runMode,
      runInProgress,
      validation,
      console,
      latestRun,
      appendConsoleLine,
      clearConsole,
      startRun: startManagedRun,
    }),
    [
      stream,
      runStatus,
      runMode,
      runInProgress,
      validation,
      console,
      latestRun,
      appendConsoleLine,
      clearConsole,
      startManagedRun,
    ],
  );
}

function describeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return typeof error === "string" ? error : "Unexpected error";
}

function calculateDurationMs(startedAt?: string | null, completedAt?: string | null): number | undefined {
  if (!startedAt || !completedAt) {
    return undefined;
  }
  const startDate = new Date(startedAt);
  const completedDate = new Date(completedAt);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(completedDate.getTime())) {
    return undefined;
  }
  return Math.max(0, completedDate.getTime() - startDate.getTime());
}

function deriveOutputMetadata({
  runResource,
  fallbackPath,
  fallbackProcessedFile,
}: {
  readonly runResource?: RunResource | null;
  readonly fallbackPath?: string | null;
  readonly fallbackProcessedFile?: string | null;
}): {
  readonly outputUrl?: string;
  readonly outputPath: string | null;
  readonly outputFilename: string | null;
  readonly outputReady: boolean | undefined;
  readonly processedFile: string | null;
} {
  const output = runResource?.output;
  const outputPath = (output?.output_path as string | null | undefined) ?? fallbackPath ?? null;
  const processedFile =
    (output?.processed_file as string | null | undefined) ??
    fallbackProcessedFile ??
    null;
  const outputUrl = runResource ? runOutputUrl(runResource) ?? undefined : undefined;
  const outputReady = output?.ready ?? (outputUrl ? true : undefined) ?? (fallbackPath ? true : undefined);
  const outputFilename =
    (output?.filename as string | null | undefined) ??
    (outputPath ? basename(outputPath) : null);

  return {
    outputUrl,
    outputPath,
    outputFilename,
    outputReady,
    processedFile,
  };
}

function extractOutputPath(artifacts: Record<string, unknown> | null): string | null {
  if (!artifacts) return null;
  if (typeof artifacts.output_path === "string") {
    return artifacts.output_path;
  }
  if (Array.isArray(artifacts.output_paths) && artifacts.output_paths.length) {
    const first = artifacts.output_paths[0];
    if (typeof first === "string") return first;
  }
  return null;
}

function extractProcessedFile(artifacts: Record<string, unknown> | null): string | null {
  if (!artifacts) return null;
  if (typeof artifacts.processed_file === "string") {
    return artifacts.processed_file;
  }
  if (Array.isArray(artifacts.processed_files) && artifacts.processed_files.length) {
    const first = artifacts.processed_files[0];
    if (typeof first === "string") return first;
  }
  return null;
}

function basename(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) return "";
  const parts = trimmed.split("/");
  return parts[parts.length - 1] || trimmed;
}

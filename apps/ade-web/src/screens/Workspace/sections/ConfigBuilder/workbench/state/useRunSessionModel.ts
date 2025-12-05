import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { isRunStatusTerminal, normalizeRunStatusValue } from "./runStream";
import { useRunStreamController, type RunStreamMetadata } from "./useRunStreamController";
import type { WorkbenchDataSeed, WorkbenchRunSummary } from "../types";

import {
  fetchRun,
  fetchRunSummary,
  fetchRunTelemetry,
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

  const consoleLines = stream.consoleLines;
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
    const artifacts =
      completedPayload.artifacts && typeof completedPayload.artifacts === "object"
        ? (completedPayload.artifacts as Record<string, unknown>)
        : null;
    const artifactOutputPath = extractOutputPath(artifacts);
    const artifactProcessedFile = extractProcessedFile(artifacts);

    const normalizedStatus = normalizeRunStatusValue(
      (completedPayload.status as RunStatus | undefined) ?? runStatus,
    );
    const completionStatus: RunStatus = normalizedStatus;
    const resolvedMode: "validation" | "extraction" = runMode ?? runMetadata?.mode ?? "extraction";
    const startedAtIso = payloadStartedAt ?? runResource?.started_at ?? runStartedAt ?? undefined;
    const completedIso = (completedPayload.completed_at as string | undefined) ?? runResource?.completed_at ?? new Date().toISOString();
    const startedAt = startedAtIso ? new Date(startedAtIso) : null;
    const completedAt = completedIso ? new Date(completedIso) : new Date();
    const durationMs =
      startedAt && completedAt ? Math.max(0, completedAt.getTime() - startedAt.getTime()) : undefined;

    onRunComplete?.({
      runId,
      status: completionStatus,
      mode: resolvedMode,
      startedAt: startedAtIso ?? null,
      completedAt: completedAt.toISOString(),
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
        outputReady: outputMeta.outputReady ?? previous?.outputReady,
        processedFile: outputMeta.processedFile,
        outputLoaded: true,
        logsUrl,
        documentName: runMetadata?.documentName,
        sheetNames: runMetadata?.sheetNames ?? [],
        summary: null,
        summaryLoaded: false,
        summaryError: null,
        telemetry: null,
        telemetryLoaded: false,
        telemetryError: null,
        error: failureMessage ?? summaryMessage ?? null,
        startedAt: startedAtIso ?? null,
        completedAt: completedAt.toISOString(),
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

      try {
        const summary = await fetchRunSummary(runId);
        setLatestRun((previous) =>
          previous && previous.runId === runId ? { ...previous, summary, summaryLoaded: true } : previous,
        );
      } catch (error) {
        setLatestRun((previous) =>
          previous && previous.runId === runId
            ? { ...previous, summaryLoaded: true, summaryError: describeError(error) }
            : previous,
        );
      }

      try {
        const telemetry = await fetchRunTelemetry(runId);
        setLatestRun((previous) =>
          previous && previous.runId === runId ? { ...previous, telemetry, telemetryLoaded: true } : previous,
        );
      } catch (error) {
        setLatestRun((previous) =>
          previous && previous.runId === runId
            ? { ...previous, telemetryLoaded: true, telemetryError: describeError(error) }
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
      consoleLines,
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
      consoleLines,
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
  const outputReady = output?.ready ?? (outputUrl ? true : undefined);
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

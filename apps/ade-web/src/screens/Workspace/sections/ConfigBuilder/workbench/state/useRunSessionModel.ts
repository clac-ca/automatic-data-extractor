import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { isRunStatusTerminal, normalizeRunStatusValue } from "./runStream";
import { useRunStreamController, type RunStreamMetadata } from "./useRunStreamController";
import type { WorkbenchDataSeed, WorkbenchRunSummary } from "../types";

import {
  fetchRun,
  fetchRunOutputs,
  fetchRunSummary,
  fetchRunTelemetry,
  runLogsUrl,
  runOutputsUrl,
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

  // Fetch outputs/telemetry/summary exactly once when a run finishes.
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

    const normalizedStatus = normalizeRunStatusValue(
      (completedPayload.status as RunStatus | undefined) ?? runStatus,
    );
    const completionStatus: RunStatus = normalizedStatus === "canceled" ? "cancelled" : normalizedStatus;
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
      const outputsBase = runResource ? runOutputsUrl(runResource) ?? undefined : previous?.outputsBase;
      const logsUrl = runResource ? runLogsUrl(runResource) ?? undefined : previous?.logsUrl;
      return {
        runId,
        status: completionStatus,
        outputsBase,
        logsUrl,
        documentName: runMetadata?.documentName,
        sheetNames: runMetadata?.sheetNames ?? [],
        outputs: [],
        outputsLoaded: false,
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
              ? { ...previous, outputsLoaded: true, summaryLoaded: true, telemetryLoaded: true, error: describeError(error) }
              : previous,
          );
        }
      }

      if (currentResource) {
        const outputsBase = runOutputsUrl(currentResource) ?? undefined;
        const logsUrl = runLogsUrl(currentResource) ?? undefined;
        setLatestRun((previous) =>
          previous && previous.runId === runId ? { ...previous, outputsBase, logsUrl } : previous,
        );
        try {
          const listing = await fetchRunOutputs(currentResource ?? runId);
          const outputFiles = Array.isArray(listing.files) ? listing.files : [];
          const files = outputFiles.map((file) => {
            const path = (file as { path?: string }).path;
            return {
              name: file.name ?? path ?? "output",
              path,
              byte_size: file.byte_size ?? 0,
              download_url: file.download_url ?? undefined,
            };
          });
          setLatestRun((previous) =>
            previous && previous.runId === runId ? { ...previous, outputs: files, outputsLoaded: true } : previous,
          );
        } catch (error) {
          setLatestRun((previous) =>
            previous && previous.runId === runId
              ? { ...previous, outputsLoaded: true, error: describeError(error) }
              : previous,
          );
        }
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

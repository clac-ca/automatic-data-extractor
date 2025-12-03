import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";

import { createRunStreamState, runStreamReducer } from "./runStream";
import {
  deriveValidationStateFromStream,
  isRunStatusInProgress,
  normalizeRunStatusValue,
  type RunStreamState,
  type RunStreamStatus,
} from "./runStream";
import type {
  WorkbenchConsoleLine,
  WorkbenchValidationMessage,
  WorkbenchValidationState,
} from "../types";
import { formatConsoleTimestamp } from "../utils/console";

import {
  createRun,
  runEventsUrl,
  streamRunEvents,
  type RunResource,
  type RunStreamOptions,
} from "@shared/runs/api";

export interface RunStreamMetadata {
  readonly mode: "validation" | "extraction";
  readonly documentId?: string;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
}

type StartRunExtras = {
  readonly forceRebuild?: boolean;
  readonly prepare?: () => boolean;
};

type UseRunStreamControllerOptions = {
  readonly configId: string;
  readonly runId: string | null;
  readonly onRunIdChange?: (runId: string | null) => void;
  readonly seed?: {
    readonly console?: readonly WorkbenchConsoleLine[];
    readonly validation?: readonly WorkbenchValidationMessage[];
  };
  readonly maxConsoleLines?: number;
  readonly onError?: (error: unknown) => void;
};

export function useRunStreamController({
  configId,
  runId,
  onRunIdChange,
  seed,
  maxConsoleLines = 400,
  onError,
}: UseRunStreamControllerOptions): {
  readonly stream: RunStreamState;
  readonly runResource?: RunResource | null;
  readonly runMetadata?: RunStreamMetadata | null;
  readonly runStartedAt?: string | null;
  readonly runStatus: RunStreamStatus;
  readonly runMode?: RunStreamMetadata["mode"];
  readonly runInProgress: boolean;
  readonly validation: WorkbenchValidationState;
  readonly appendConsoleLine: (line: WorkbenchConsoleLine) => void;
  readonly clearConsole: () => void;
  readonly startRun: (
    options: RunStreamOptions,
    metadata: RunStreamMetadata,
    extras?: StartRunExtras,
  ) => Promise<{ runId: string; startedAt: string } | null>;
} {
  const initialState = useMemo(() => {
    const seeded =
      Boolean(seed?.console && seed.console.length > 0) ||
      Boolean(seed?.validation && seed.validation.length > 0);
    const base = createRunStreamState(
      maxConsoleLines,
      seed?.console ? [...seed.console].slice(-maxConsoleLines) : undefined,
      seeded,
    );
    if (seed?.validation?.length) {
      return {
        ...base,
        runMode: "validation",
        validationSummary: { issues: [...seed.validation] },
      };
    }
    return base;
  }, [maxConsoleLines, seed?.console, seed?.validation]);
  const [stream, dispatch] = useReducer(runStreamReducer, initialState);
  const streamRef = useRef<RunStreamState>(stream);
  const runResourceRef = useRef<RunResource | null>(null);
  const runMetadataRef = useRef<RunStreamMetadata | null>(null);
  const runStartedAtRef = useRef<string | null>(null);
  const streamControllerRef = useRef<AbortController | null>(null);
  const startInFlightRef = useRef(false);

  useEffect(() => {
    streamRef.current = stream;
  }, [stream]);

  const stopStreaming = useCallback(() => {
    const controller = streamControllerRef.current;
    if (controller) {
      controller.abort();
      streamControllerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (runId !== null) {
      return;
    }
    stopStreaming();
    runResourceRef.current = null;
    runMetadataRef.current = null;
    runStartedAtRef.current = null;
  }, [runId, stopStreaming]);

  const appendConsoleLine = useCallback(
    (line: WorkbenchConsoleLine) => dispatch({ type: "APPEND_LINE", line }),
    [dispatch],
  );

  const clearConsole = useCallback(() => {
    dispatch({ type: "CLEAR_CONSOLE" });
  }, [dispatch]);

  const pushError = useCallback(
    (error: unknown) => {
      if (onError) {
        onError(error);
        return;
      }
      appendConsoleLine({
        level: "error",
        message: describeError(error),
        timestamp: formatConsoleTimestamp(new Date()),
        origin: "run",
      });
    },
    [appendConsoleLine, onError],
  );

  const connectToRun = useCallback(
    async (runResource: RunResource, metadata?: RunStreamMetadata | null) => {
      stopStreaming();
      const eventsUrl = runEventsUrl(runResource);
      if (!eventsUrl) {
        throw new Error("Run events link unavailable.");
      }
      runResourceRef.current = runResource;
      runMetadataRef.current = metadata ?? null;
      runStartedAtRef.current = runResource.started_at ?? runStartedAtRef.current ?? null;
      dispatch({ type: "ATTACH_RUN", runId: runResource.id, runMode: metadata?.mode });
      const controller = new AbortController();
      streamControllerRef.current = controller;
      try {
        for await (const event of streamRunEvents(eventsUrl, controller.signal)) {
          dispatch({ type: "EVENT", event });
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          pushError(error);
        }
      } finally {
        if (streamControllerRef.current === controller) {
          streamControllerRef.current = null;
        }
      }
    },
    [pushError, stopStreaming],
  );

  const resolvedStatus = normalizeRunStatusValue(stream.status);
  const runMode = stream.runMode ?? runMetadataRef.current?.mode;
  const runInProgress = isRunStatusInProgress(resolvedStatus);

  const validation = useMemo(() => deriveValidationStateFromStream(stream, seed?.validation), [stream, seed?.validation]);

  const startRun = useCallback(
    async (
      options: RunStreamOptions,
      metadata: RunStreamMetadata,
      extras?: StartRunExtras,
    ): Promise<{ runId: string; startedAt: string } | null> => {
      const forceRebuild = extras?.forceRebuild ?? false;
      const effectiveOptions = forceRebuild ? { ...options, force_rebuild: true } : options;
      if (runInProgress || startInFlightRef.current) {
        return null;
      }
      if (extras?.prepare && extras.prepare() === false) {
        return null;
      }

      const startedAt = new Date();
      dispatch({
        type: "RESET",
        runId: null,
        initialLines: [
          {
            level: "info",
            message:
              metadata.mode === "validation"
                ? "Starting ADE run (validate-only)…"
                : "Starting ADE extraction…",
            timestamp: formatConsoleTimestamp(startedAt),
            origin: "run",
          },
        ],
      });

      startInFlightRef.current = true;
      try {
        const resource = await createRun(configId, effectiveOptions);
        runMetadataRef.current = metadata;
        runStartedAtRef.current = startedAt.toISOString();
        onRunIdChange?.(resource.id);
        await connectToRun(resource, metadata);
        return { runId: resource.id, startedAt: startedAt.toISOString() };
      } catch (error) {
        pushError(error);
        return null;
      } finally {
        startInFlightRef.current = false;
      }
    },
    [configId, connectToRun, dispatch, onRunIdChange, pushError, runInProgress],
  );

  useEffect(
    () => () => {
      stopStreaming();
    },
    [stopStreaming],
  );

  return {
    stream,
    runResource: runResourceRef.current,
    runMetadata: runMetadataRef.current,
    runStartedAt: runStartedAtRef.current,
    runStatus: resolvedStatus,
    runMode,
    runInProgress,
    validation,
    appendConsoleLine,
    clearConsole,
    startRun,
  };
}

function describeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return typeof error === "string" ? error : "Unexpected error";
}

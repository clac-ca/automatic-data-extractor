import { useCallback, useSyncExternalStore } from "react";

import {
  createRun,
  fetchRun,
  fetchRunEvents,
  runEventsUrl,
  streamRunEvents,
  type RunResource,
  type RunStreamOptions,
} from "./api";
import type { RunStreamEvent } from "./types";

type RunJobConnectState = "idle" | "connecting" | "streaming" | "error";

export type RunJobMode = "validation" | "extraction";

export interface RunJobState {
  readonly runId: string;
  readonly resource?: RunResource;
  readonly events: RunStreamEvent[];
  readonly lastSequence: number;
  readonly status: RunStatus;
  readonly mode?: RunJobMode;
  readonly connectState: RunJobConnectState;
  readonly error?: string | null;
  readonly startedAt?: string;
  readonly metadata?: {
    documentId?: string;
    documentName?: string;
    sheetNames?: readonly string[];
  };
}

export type RunStatus =
  | "idle"
  | "queued"
  | "waiting_for_build"
  | "building"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

type RunJobStoreState = {
  runs: Map<string, RunJobState>;
};

type Listener = () => void;

const store: RunJobStoreState = {
  runs: new Map(),
};

const listeners = new Set<Listener>();
const streamControllers = new Map<string, AbortController>();
const retryTimers = new Map<string, ReturnType<typeof setTimeout>>();
const pendingStreams = new Set<string>();

function notify() {
  listeners.forEach((listener) => listener());
}

function getRun(runId: string | null | undefined): RunJobState | undefined {
  if (!runId) return undefined;
  return store.runs.get(runId);
}

function setRun(runId: string, next: RunJobState) {
  store.runs.set(runId, next);
  notify();
}

function updateRun(runId: string, updater: (prev: RunJobState | undefined) => RunJobState) {
  const prev = getRun(runId);
  const next = updater(prev);
  setRun(runId, next);
}

function normalizeRunStatus(value: unknown): RunStatus {
  if (value === "queued") return "queued";
  if (value === "waiting_for_build") return "waiting_for_build";
  if (value === "building") return "building";
  if (value === "running") return "running";
  if (value === "succeeded") return "succeeded";
  if (value === "failed") return "failed";
  if (value === "cancelled") return "cancelled";
  return "idle";
}

function isTerminal(status: RunStatus) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

function mergeEvents(prevEvents: RunStreamEvent[], nextEvents: RunStreamEvent[]) {
  const seen = new Set<number>();
  const merged: RunStreamEvent[] = [];
  const push = (event: RunStreamEvent) => {
    const seq = typeof event.sequence === "number" ? event.sequence : undefined;
    if (seq != null) {
      if (seen.has(seq)) return;
      seen.add(seq);
    }
    merged.push(event);
  };
  // Keep previous order, then new events.
  prevEvents.forEach((event) => push(event));
  nextEvents.forEach((event) => push(event));
  merged.sort((a, b) => {
    const seqA = typeof a.sequence === "number" ? a.sequence : 0;
    const seqB = typeof b.sequence === "number" ? b.sequence : 0;
    return seqA - seqB;
  });
  return merged;
}

function reduceStatus(current: RunStatus, event: RunStreamEvent): RunStatus {
  const type = event?.type ?? "";
  const payload = (event?.payload ?? {}) as Record<string, unknown>;
  switch (type) {
    case "run.queued":
      return "queued";
    case "run.waiting_for_build":
      return "waiting_for_build";
    case "build.start":
    case "build.started":
      return "building";
    case "run.start":
    case "run.started":
    case "engine.start":
      return "running";
    case "run.complete":
    case "engine.complete": {
      const statusValue =
        (payload.status as string | undefined) ??
        (payload.engine_status as string | undefined);
      return normalizeRunStatus(statusValue);
    }
    case "run.error":
      return current === "failed" ? current : "failed";
    default:
      return current;
  }
}

function deriveMode(event: RunStreamEvent, prev?: RunJobMode) {
  const payload = (event?.payload ?? {}) as Record<string, unknown>;
  const mode = payload.mode;
  if (mode === "validation" || mode === "extraction") {
    return mode;
  }
  return prev;
}

function handleEvents(runId: string, events: RunStreamEvent[]) {
  updateRun(runId, (prev) => {
    const base: RunJobState =
      prev ??
      ({
        runId,
        events: [],
        lastSequence: 0,
        status: "idle",
        connectState: "idle",
      } satisfies RunJobState);

    const mergedEvents = mergeEvents(base.events, events);
    const lastSequence = mergedEvents.reduce((max, event) => {
      const seq = typeof event.sequence === "number" ? event.sequence : max;
      return seq > max ? seq : max;
    }, base.lastSequence);

    const nextStatus = events.reduce((status, event) => reduceStatus(status, event), base.status);
    const mode = events.reduce((current, event) => deriveMode(event, current), base.mode);

    return {
      ...base,
      events: mergedEvents,
      lastSequence,
      status: nextStatus,
      mode,
    };
  });
}

function handleResource(resource: RunResource) {
  const runId = resource.id;
  updateRun(runId, (prev) => {
    const status = normalizeRunStatus(resource.status);
    return {
      runId,
      resource,
      events: prev?.events ?? [],
      lastSequence: prev?.lastSequence ?? 0,
      status: isTerminal(prev?.status ?? "idle") ? prev!.status : status,
      mode: prev?.mode,
      connectState: prev?.connectState ?? "idle",
      error: prev?.error,
      startedAt: prev?.startedAt ?? resource.started_at ?? undefined,
      metadata: prev?.metadata,
    };
  });
}

function stopRunStream(runId: string) {
  const controller = streamControllers.get(runId);
  if (controller) {
    controller.abort();
  }
  streamControllers.delete(runId);
  const retry = retryTimers.get(runId);
  if (retry) {
    clearTimeout(retry);
    retryTimers.delete(runId);
  }
}

async function ensureRunStream(runId: string) {
  const existing = getRun(runId);
  if (!existing || streamControllers.has(runId)) {
    return;
  }
  if (pendingStreams.has(runId)) {
    return;
  }
  pendingStreams.add(runId);

  const resource = existing.resource ?? (await fetchRun(runId).catch(() => undefined));
  if (!resource) {
    updateRun(runId, (prev) => ({
      ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
      connectState: "error",
      error: "Run resource unavailable.",
    }));
    pendingStreams.delete(runId);
    return;
  }

  // Hydrate history before streaming live events.
  try {
    const history = await fetchRunEvents(resource, { afterSequence: existing.lastSequence });
    if (history.length) {
      handleEvents(runId, history);
    }
  } catch (error) {
    console.warn("Run history unavailable", error);
  }

  const current = getRun(runId) ?? existing;
  const eventsUrl = runEventsUrl(resource, { afterSequence: current.lastSequence });
  if (!eventsUrl) {
    updateRun(runId, (prev) => ({
      ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
      connectState: "error",
      error: "Run events unavailable.",
    }));
    pendingStreams.delete(runId);
    return;
  }

  const controller = new AbortController();
  streamControllers.set(runId, controller);

  updateRun(runId, (prev) => ({
    ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
    connectState: "connecting",
      error: null,
      resource,
    }));

  try {
    for await (const event of streamRunEvents(eventsUrl, controller.signal)) {
      handleEvents(runId, [event]);
      updateRun(runId, (prev) => ({
        ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
        connectState: "streaming",
      }));
    }
    stopRunStream(runId);
    updateRun(runId, (prev) => ({
      ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
      connectState: "idle",
    }));
  } catch (error) {
    if (controller.signal.aborted) {
      pendingStreams.delete(runId);
      return;
    }
    console.warn("Run stream interrupted", error);
    stopRunStream(runId);
    updateRun(runId, (prev) => ({
      ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
      connectState: "error",
      error: error instanceof Error ? error.message : "Run stream interrupted",
    }));
    const current = getRun(runId);
    if (current && !isTerminal(current.status)) {
      const retry = setTimeout(() => {
        retryTimers.delete(runId);
        void ensureRunStream(runId);
      }, 1500);
      retryTimers.set(runId, retry);
    }
  }
  pendingStreams.delete(runId);
}

export async function startRunJob(
  configId: string,
  options: RunStreamOptions,
  metadata?: RunJobState["metadata"] & { mode?: RunJobMode },
): Promise<RunJobState> {
  const resource = await createRun(configId, options);
  const runId = resource.id;
  const mode = metadata?.mode;
  const startedAt = new Date().toISOString();
  setRun(runId, {
    runId,
    resource,
    events: [],
    lastSequence: 0,
    status: normalizeRunStatus(resource.status),
    connectState: "idle",
    mode,
    startedAt,
    metadata,
  });
  void ensureRunStream(runId);
  return getRun(runId)!;
}

export async function connectRunJob(runId: string) {
  const existing = getRun(runId);
  if (!existing?.resource) {
    try {
      const resource = await fetchRun(runId);
      handleResource(resource);
    } catch (error) {
      updateRun(runId, (prev) => ({
        ...(prev ?? { runId, events: [], lastSequence: 0, status: "idle", connectState: "idle" }),
        connectState: "error",
        error: error instanceof Error ? error.message : "Unable to load run",
      }));
      return;
    }
  }
  void ensureRunStream(runId);
}

export function useRunJob(runId: string | null | undefined): RunJobState | undefined {
  const subscribe = useCallback((listener: Listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }, []);

  const getSnapshot = useCallback(() => getRun(runId), [runId]);

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function resetRunJob(runId: string) {
  stopRunStream(runId);
  store.runs.delete(runId);
  notify();
}

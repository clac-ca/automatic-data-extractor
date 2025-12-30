import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@shared/api/errors";

import {
  cancelDocumentUploadSession,
  commitDocumentUploadSession,
  createDocumentUploadSession,
  getDocumentUploadSessionStatus,
  uploadDocumentUploadSessionRange,
  uploadWorkspaceDocument,
  type DocumentUploadResponse,
  type DocumentUploadRunOptions,
} from "./uploads";

export type UploadManagerStatus =
  | "queued"
  | "uploading"
  | "paused"
  | "succeeded"
  | "failed"
  | "cancelled";

export type UploadManagerProgress = {
  readonly loaded: number;
  readonly total: number;
  readonly percent: number;
};

export interface UploadManagerItem<TResponse> {
  readonly id: string;
  readonly file: File;
  readonly status: UploadManagerStatus;
  readonly progress: UploadManagerProgress;
  readonly runOptions?: DocumentUploadRunOptions;
  readonly response?: TResponse;
  readonly error?: string;
  readonly mode?: "simple" | "session";
  readonly sessionId?: string;
  readonly chunkSizeBytes?: number;
  readonly nextExpectedRanges?: string[];
}

export type UploadManagerQueueItem = {
  readonly file: File;
  readonly runOptions?: DocumentUploadRunOptions;
};

export type UploadManagerSummary = {
  readonly totalCount: number;
  readonly queuedCount: number;
  readonly uploadingCount: number;
  readonly pausedCount: number;
  readonly succeededCount: number;
  readonly failedCount: number;
  readonly cancelledCount: number;
  readonly completedCount: number;
  readonly totalBytes: number;
  readonly uploadedBytes: number;
  readonly percent: number;
  readonly inFlightCount: number;
};

interface UseUploadManagerOptions {
  readonly workspaceId: string;
  readonly concurrency?: number;
  readonly sessionThresholdBytes?: number;
}

const DEFAULT_CONCURRENCY = 3;
const DEFAULT_SESSION_THRESHOLD_BYTES = 10 * 1024 * 1024;
const FALLBACK_CHUNK_BYTES = 5 * 1024 * 1024;

export function useUploadManager({
  workspaceId,
  concurrency = DEFAULT_CONCURRENCY,
  sessionThresholdBytes = DEFAULT_SESSION_THRESHOLD_BYTES,
}: UseUploadManagerOptions) {
  const [items, setItems] = useState<UploadManagerItem<DocumentUploadResponse>[]>([]);
  const inFlightRef = useRef(new Set<string>());
  const abortHandlesRef = useRef(new Map<string, () => void>());
  const abortReasonsRef = useRef(new Map<string, "pause" | "cancel">());

  const enqueue = useCallback((files: readonly UploadManagerQueueItem[]) => {
    if (!files.length) return [];
    const now = Date.now();
    const newItems = files.map((entry, index) => ({
      id: createUploadId(now, index),
      file: entry.file,
      status: "queued" as const,
      runOptions: entry.runOptions,
      progress: {
        loaded: 0,
        total: Math.max(entry.file.size, 0),
        percent: 0,
      },
    }));
    setItems((current) => [...current, ...newItems]);
    return newItems;
  }, []);

  const pause = useCallback((itemId: string) => {
    abortReasonsRef.current.set(itemId, "pause");
    const abort = abortHandlesRef.current.get(itemId);
    if (abort) {
      abort();
    }
    setItems((current) =>
      current.map((item) =>
        item.id === itemId && item.status === "uploading"
          ? { ...item, status: "paused" }
          : item,
      ),
    );
  }, []);

  const resume = useCallback((itemId: string) => {
    setItems((current) =>
      current.map((item) => {
        if (item.id !== itemId) return item;
        if (item.status !== "paused") return item;
        if (item.mode === "simple") {
          return {
            ...item,
            status: "queued",
            progress: resetProgress(item.file),
          };
        }
        return { ...item, status: "queued" };
      }),
    );
  }, []);

  const retry = useCallback((itemId: string) => {
    setItems((current) =>
      current.map((item) => {
        if (item.id !== itemId) return item;
        if (item.status !== "failed") return item;
        if (item.mode === "simple") {
          return {
            ...item,
            status: "queued",
            progress: resetProgress(item.file),
            error: undefined,
            response: undefined,
          };
        }
        return {
          ...item,
          status: "queued",
          error: undefined,
        };
      }),
    );
  }, []);

  const cancel = useCallback(
    (itemId: string) => {
      abortReasonsRef.current.set(itemId, "cancel");
      const abort = abortHandlesRef.current.get(itemId);
      if (abort) {
        abort();
      }
      setItems((current) =>
        current.map((item) =>
          item.id === itemId && item.status !== "succeeded"
            ? { ...item, status: "cancelled" }
            : item,
        ),
      );
      const item = items.find((entry) => entry.id === itemId);
      if (item?.sessionId) {
        void cancelDocumentUploadSession(workspaceId, item.sessionId).catch(() => null);
      }
    },
    [items, workspaceId],
  );

  const remove = useCallback(
    (itemId: string) => {
      cancel(itemId);
      setItems((current) => current.filter((item) => item.id !== itemId));
    },
    [cancel],
  );

  const clearCompleted = useCallback(() => {
    setItems((current) => current.filter((item) => !isTerminalStatus(item.status)));
  }, []);

  useEffect(() => {
    if (!workspaceId) {
      return;
    }
    const activeCount = items.filter((item) => item.status === "uploading").length;
    if (activeCount >= concurrency) {
      return;
    }

    const availableSlots = concurrency - activeCount;
    const queuedItems = items.filter((item) => item.status === "queued").slice(0, availableSlots);

    for (const item of queuedItems) {
      if (inFlightRef.current.has(item.id)) {
        continue;
      }
      inFlightRef.current.add(item.id);
      const mode = item.mode ?? (item.file.size >= sessionThresholdBytes ? "session" : "simple");
      setItems((current) =>
        current.map((entry) =>
          entry.id === item.id
            ? {
                ...entry,
                status: "uploading",
                mode,
              }
            : entry,
        ),
      );

      const controller = new AbortController();
      abortHandlesRef.current.set(item.id, () => controller.abort());

      const uploadPromise =
        mode === "session"
          ? runSessionUpload(item, {
              workspaceId,
              controller,
              updateItem: (patch) =>
                setItems((current) =>
                  current.map((entry) => (entry.id === item.id ? { ...entry, ...patch } : entry)),
                ),
            })
          : runSimpleUpload(item, {
              workspaceId,
              controller,
              onProgress: (progress) =>
                setItems((current) =>
                  current.map((entry) =>
                    entry.id === item.id
                      ? {
                          ...entry,
                          progress: normalizeProgress(entry.file, progress),
                        }
                      : entry,
                  ),
                ),
            });

      uploadPromise
        .then((result) => {
          setItems((current) =>
            current.map((entry) =>
              entry.id === item.id
                ? {
                    ...entry,
                    status: "succeeded",
                    progress: completeProgress(entry.file),
                    response: result,
                    error: undefined,
                  }
                : entry,
            ),
          );
        })
        .catch((error) => {
          const abortReason = abortReasonsRef.current.get(item.id);
          const errorName = error instanceof Error ? error.name : "";
          const isAbort = errorName === "AbortError";
          if (isAbort && abortReason) {
            return;
          }
          const message =
            error instanceof Error ? error.message : "Upload failed.";
          setItems((current) =>
            current.map((entry) =>
              entry.id === item.id
                ? {
                    ...entry,
                    status: isAbort ? "cancelled" : "failed",
                    error: message,
                  }
                : entry,
            ),
          );
        })
        .finally(() => {
          inFlightRef.current.delete(item.id);
          abortHandlesRef.current.delete(item.id);
          abortReasonsRef.current.delete(item.id);
        });
    }
  }, [concurrency, items, sessionThresholdBytes, workspaceId]);

  const summary = useMemo<UploadManagerSummary>(() => {
    let totalBytes = 0;
    let uploadedBytes = 0;
    let queuedCount = 0;
    let uploadingCount = 0;
    let pausedCount = 0;
    let succeededCount = 0;
    let failedCount = 0;
    let cancelledCount = 0;

    for (const item of items) {
      totalBytes += Math.max(item.file.size, 0);
      uploadedBytes += item.progress.loaded;
      switch (item.status) {
        case "queued":
          queuedCount += 1;
          break;
        case "uploading":
          uploadingCount += 1;
          break;
        case "paused":
          pausedCount += 1;
          break;
        case "succeeded":
          succeededCount += 1;
          break;
        case "failed":
          failedCount += 1;
          break;
        case "cancelled":
          cancelledCount += 1;
          break;
        default:
          break;
      }
    }

    const completedCount = succeededCount + failedCount + cancelledCount;
    const inFlightCount = queuedCount + uploadingCount + pausedCount;
    const percent = totalBytes > 0 ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 0;

    return {
      totalCount: items.length,
      queuedCount,
      uploadingCount,
      pausedCount,
      succeededCount,
      failedCount,
      cancelledCount,
      completedCount,
      totalBytes,
      uploadedBytes,
      percent,
      inFlightCount,
    };
  }, [items]);

  return {
    items,
    summary,
    enqueue,
    pause,
    resume,
    retry,
    cancel,
    remove,
    clearCompleted,
  };
}

function normalizeProgress(file: File, progress: { loaded: number; total: number | null }) {
  const total = progress.total ?? Math.max(file.size, 0);
  const loaded = Math.max(progress.loaded, 0);
  const percent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
  return { loaded, total, percent };
}

function resetProgress(file: File): UploadManagerProgress {
  const total = Math.max(file.size, 0);
  return { loaded: 0, total, percent: total > 0 ? 0 : 0 };
}

function completeProgress(file: File): UploadManagerProgress {
  const total = Math.max(file.size, 0);
  return { loaded: total, total, percent: total > 0 ? 100 : 0 };
}

function isTerminalStatus(status: UploadManagerStatus) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

function createUploadId(seed: number, index: number) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `upload-${seed}-${index}-${Math.random().toString(36).slice(2, 9)}`;
}

async function runSimpleUpload(
  item: UploadManagerItem<DocumentUploadResponse>,
  options: {
    workspaceId: string;
    controller: AbortController;
    onProgress: (progress: { loaded: number; total: number | null }) => void;
  },
) {
  const handle = uploadWorkspaceDocument(options.workspaceId, item.file, {
    onProgress: options.onProgress,
    runOptions: item.runOptions,
  });
  options.controller.signal.addEventListener("abort", () => handle.abort(), { once: true });
  const result = await handle.promise;
  if (!result.data) {
    throw new Error("Expected upload response.");
  }
  return result.data;
}

async function runSessionUpload(
  item: UploadManagerItem<DocumentUploadResponse>,
  options: {
    workspaceId: string;
    controller: AbortController;
    updateItem: (patch: Partial<UploadManagerItem<DocumentUploadResponse>>) => void;
  },
) {
  const total = Math.max(item.file.size, 0);
  let sessionId = item.sessionId;
  let chunkSize = item.chunkSizeBytes ?? FALLBACK_CHUNK_BYTES;
  let receivedBytes = Math.min(item.progress.loaded, total);

  if (sessionId) {
    try {
      const status = await getDocumentUploadSessionStatus(
        options.workspaceId,
        sessionId,
        options.controller.signal,
      );
      receivedBytes = Math.min(status.received_bytes ?? receivedBytes, total);
      options.updateItem({
        sessionId: status.upload_session_id,
        nextExpectedRanges: status.next_expected_ranges,
        progress: {
          loaded: receivedBytes,
          total,
          percent: total > 0 ? Math.min(100, Math.round((receivedBytes / total) * 100)) : 0,
        },
      });
    } catch (error) {
      if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
        sessionId = undefined;
        receivedBytes = 0;
        options.updateItem({
          sessionId: undefined,
          nextExpectedRanges: undefined,
          progress: resetProgress(item.file),
        });
      } else {
        throw error;
      }
    }
  }

  if (!sessionId) {
    const created = await createDocumentUploadSession(
      options.workspaceId,
      {
        filename: item.file.name,
        byte_size: total,
        content_type: item.file.type || undefined,
        run_options: item.runOptions,
      },
      options.controller.signal,
    );
    sessionId = created.upload_session_id;
    chunkSize = created.chunk_size_bytes ?? chunkSize;
    receivedBytes = 0;
    options.updateItem({
      sessionId,
      chunkSizeBytes: chunkSize,
      nextExpectedRanges: created.next_expected_ranges,
      progress: resetProgress(item.file),
    });
  }

  while (receivedBytes < total) {
    if (options.controller.signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const end = Math.min(receivedBytes + chunkSize - 1, total - 1);
    const chunk = item.file.slice(receivedBytes, end + 1);
    const response = await uploadDocumentUploadSessionRange(
      options.workspaceId,
      sessionId,
      {
        start: receivedBytes,
        end,
        total,
        body: chunk,
        signal: options.controller.signal,
      },
    );
    receivedBytes = end + 1;
    options.updateItem({
      nextExpectedRanges: response.next_expected_ranges,
      progress: {
        loaded: receivedBytes,
        total,
        percent: total > 0 ? Math.min(100, Math.round((receivedBytes / total) * 100)) : 0,
      },
    });
  }

  const committed = await commitDocumentUploadSession(
    options.workspaceId,
    sessionId,
    options.controller.signal,
  );
  return committed;
}

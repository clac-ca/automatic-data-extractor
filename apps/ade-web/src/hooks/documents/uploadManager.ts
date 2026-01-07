import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  uploadWorkspaceDocument,
  type DocumentUploadResponse,
  type DocumentUploadRunOptions,
} from "@api/documents/uploads";

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
}

const DEFAULT_CONCURRENCY = 3;

export function useUploadManager({
  workspaceId,
  concurrency = DEFAULT_CONCURRENCY,
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
        return {
          ...item,
          status: "queued",
          progress: resetProgress(item.file),
        };
      }),
    );
  }, []);

  const retry = useCallback((itemId: string) => {
    setItems((current) =>
      current.map((item) => {
        if (item.id !== itemId) return item;
        if (item.status !== "failed") return item;
        return {
          ...item,
          status: "queued",
          progress: resetProgress(item.file),
          error: undefined,
          response: undefined,
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
    },
    [],
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

  const updateResponse = useCallback((itemId: string, response: DocumentUploadResponse) => {
    setItems((current) => current.map((item) => (item.id === itemId ? { ...item, response } : item)));
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
      setItems((current) =>
        current.map((entry) =>
          entry.id === item.id
            ? {
                ...entry,
                status: "uploading",
              }
            : entry,
        ),
      );

      const controller = new AbortController();
      abortHandlesRef.current.set(item.id, () => controller.abort());

      const uploadPromise = runSimpleUpload(item, {
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
  }, [concurrency, items, workspaceId]);

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
    updateResponse,
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
    idempotencyKey: item.id,
    runOptions: item.runOptions,
  });
  options.controller.signal.addEventListener("abort", () => handle.abort(), { once: true });
  const result = await handle.promise;
  if (!result.data) {
    throw new Error("Expected upload response.");
  }
  return result.data;
}

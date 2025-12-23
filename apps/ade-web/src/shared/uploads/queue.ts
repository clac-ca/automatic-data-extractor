import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { UploadHandle, UploadProgress } from "./xhr";

export type UploadStatus = "queued" | "uploading" | "succeeded" | "failed" | "cancelled";

export type UploadQueueProgress = {
  readonly loaded: number;
  readonly total: number;
  readonly percent: number;
};

export interface UploadQueueItem<TResponse> {
  readonly id: string;
  readonly file: File;
  readonly status: UploadStatus;
  readonly progress: UploadQueueProgress;
  readonly response?: TResponse;
  readonly error?: string;
}

export type UploadStarter<TResponse> = (
  file: File,
  handlers: { onProgress: (progress: UploadProgress) => void },
) => UploadHandle<TResponse>;

export type UploadQueueSummary = {
  readonly totalCount: number;
  readonly queuedCount: number;
  readonly uploadingCount: number;
  readonly succeededCount: number;
  readonly failedCount: number;
  readonly cancelledCount: number;
  readonly completedCount: number;
  readonly totalBytes: number;
  readonly uploadedBytes: number;
  readonly percent: number;
  readonly inFlightCount: number;
};

interface UseUploadQueueOptions<TResponse> {
  readonly concurrency?: number;
  readonly startUpload: UploadStarter<TResponse>;
}

export function useUploadQueue<TResponse>({
  concurrency = 3,
  startUpload,
}: UseUploadQueueOptions<TResponse>) {
  const [items, setItems] = useState<UploadQueueItem<TResponse>[]>([]);
  const inFlightRef = useRef(new Set<string>());
  const abortHandlesRef = useRef(new Map<string, () => void>());

  const enqueue = useCallback((files: readonly File[]) => {
    if (!files.length) return [];
    const now = Date.now();
    const newItems = files.map((file, index) => {
      const id = createUploadId(now, index);
      return {
        id,
        file,
        status: "queued" as const,
        progress: {
          loaded: 0,
          total: Math.max(file.size, 0),
          percent: 0,
        },
      };
    });
    setItems((current) => [...current, ...newItems]);
    return newItems;
  }, []);

  const cancel = useCallback((itemId: string) => {
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
  }, []);

  const retry = useCallback((itemId: string) => {
    setItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              status: "queued",
              progress: { loaded: 0, total: Math.max(item.file.size, 0), percent: 0 },
              response: undefined,
              error: undefined,
            }
          : item,
      ),
    );
  }, []);

  const remove = useCallback((itemId: string) => {
    cancel(itemId);
    setItems((current) => current.filter((item) => item.id !== itemId));
  }, [cancel]);

  const clearCompleted = useCallback(() => {
    setItems((current) => current.filter((item) => !isTerminalStatus(item.status)));
  }, []);

  useEffect(() => {
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
          entry.id === item.id ? { ...entry, status: "uploading" } : entry,
        ),
      );

      const handle = startUpload(item.file, {
        onProgress: (progress) => {
          setItems((current) =>
            current.map((entry) =>
              entry.id === item.id
                ? {
                    ...entry,
                    progress: normalizeProgress(entry.file, progress),
                  }
                : entry,
            ),
          );
        },
      });
      abortHandlesRef.current.set(item.id, handle.abort);

      handle.promise
        .then((result) => {
          setItems((current) =>
            current.map((entry) =>
              entry.id === item.id
                ? {
                    ...entry,
                    status: "succeeded",
                    progress: completeProgress(entry.file),
                    response: result.data ?? undefined,
                    error: undefined,
                  }
                : entry,
            ),
          );
        })
        .catch((error) => {
          const errorName = error instanceof Error ? error.name : "";
          const isAbort = errorName === "AbortError";
          const message = !isAbort
            ? error instanceof Error
              ? error.message
              : "Upload failed."
            : undefined;
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
        });
    }
  }, [concurrency, items, startUpload]);

  const summary = useMemo<UploadQueueSummary>(() => {
    let totalBytes = 0;
    let uploadedBytes = 0;
    let queuedCount = 0;
    let uploadingCount = 0;
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
    const inFlightCount = queuedCount + uploadingCount;
    const percent = totalBytes > 0 ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 0;

    return {
      totalCount: items.length,
      queuedCount,
      uploadingCount,
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
    cancel,
    retry,
    remove,
    clearCompleted,
  };
}

function normalizeProgress(file: File, progress: UploadProgress): UploadQueueProgress {
  const total = progress.total ?? Math.max(file.size, 0);
  const loaded = Math.max(progress.loaded, 0);
  const percent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
  return { loaded, total, percent };
}

function completeProgress(file: File): UploadQueueProgress {
  const total = Math.max(file.size, 0);
  return {
    loaded: total,
    total,
    percent: total > 0 ? 100 : 0,
  };
}

function isTerminalStatus(status: UploadStatus) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

function createUploadId(seed: number, index: number) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `upload-${seed}-${index}-${Math.random().toString(36).slice(2, 9)}`;
}

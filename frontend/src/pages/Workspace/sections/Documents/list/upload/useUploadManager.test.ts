import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/errors";

import { useUploadManager } from "./useUploadManager";

const uploadWorkspaceDocumentMock = vi.fn();

vi.mock("@/api/documents/uploads", () => ({
  uploadWorkspaceDocument: (...args: unknown[]) =>
    uploadWorkspaceDocumentMock(...args),
}));

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolveFn, rejectFn) => {
    resolve = resolveFn;
    reject = rejectFn;
  });
  return { promise, resolve, reject };
}

function createFile(name: string, size = 64) {
  const bytes = new Uint8Array(size);
  return new File([bytes], name, { type: "text/csv" });
}

describe("useUploadManager", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("aborts active uploads and clears queue when workspace changes", async () => {
    const uploads: Array<{ deferred: Deferred<{ data: unknown }>; abort: ReturnType<typeof vi.fn> }> = [];
    uploadWorkspaceDocumentMock.mockImplementation(() => {
      const deferred = createDeferred<{ data: unknown }>();
      const abort = vi.fn(() => {
        deferred.reject(new DOMException("Aborted", "AbortError"));
      });
      uploads.push({ deferred, abort });
      return { promise: deferred.promise, abort };
    });

    const { result, rerender } = renderHook(
      ({ workspaceId }) => useUploadManager({ workspaceId, concurrency: 1 }),
      { initialProps: { workspaceId: "ws_1" } },
    );

    act(() => {
      result.current.enqueue([{ file: createFile("pending.csv") }]);
    });

    await waitFor(() => {
      expect(uploadWorkspaceDocumentMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe("uploading");
    });

    rerender({ workspaceId: "ws_2" });

    expect(uploads[0]?.abort).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(result.current.items).toHaveLength(0);
    });
  });

  it("counts conflict items and retries all conflicts with selected mode", async () => {
    const uploads: Array<{ deferred: Deferred<{ data: unknown }> }> = [];
    uploadWorkspaceDocumentMock.mockImplementation(() => {
      const deferred = createDeferred<{ data: unknown }>();
      uploads.push({ deferred });
      return { promise: deferred.promise, abort: vi.fn() };
    });

    const { result } = renderHook(() =>
      useUploadManager({ workspaceId: "ws_1", concurrency: 1 }),
    );

    act(() => {
      result.current.enqueue([{ file: createFile("dupe.csv") }]);
    });

    await waitFor(() => {
      expect(uploadWorkspaceDocumentMock).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      uploads[0]?.deferred.reject(new ApiError("Conflict", 409, { detail: "already exists" } as never));
    });

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe("conflict");
    });

    expect(result.current.items[0]?.error).toBeUndefined();
    expect(result.current.summary.conflictCount).toBe(1);
    expect(result.current.summary.inFlightCount).toBe(1);
    expect(result.current.summary.failedCount).toBe(0);

    act(() => {
      result.current.resolveAllConflicts("keep_both");
    });

    await waitFor(() => {
      expect(uploadWorkspaceDocumentMock).toHaveBeenCalledTimes(2);
    });

    const secondCallOptions = uploadWorkspaceDocumentMock.mock.calls[1]?.[2] as
      | { conflictMode?: string }
      | undefined;
    expect(secondCallOptions?.conflictMode).toBe("keep_both");

    await act(async () => {
      uploads[1]?.deferred.resolve({ data: { id: "doc_1" } });
    });

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe("succeeded");
    });
  });
});

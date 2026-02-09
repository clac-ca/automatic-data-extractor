import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useUploadQueue } from "@/lib/uploads/queue";

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

function createFile(name: string, size: number) {
  const bytes = new Uint8Array(size);
  return new File([bytes], name, { type: "text/plain" });
}

describe("useUploadQueue", () => {
  it("respects concurrency limits", async () => {
    const uploads: Array<{
      deferred: Deferred<{ data: string | null; status: number }>;
      abort: ReturnType<typeof vi.fn>;
    }> = [];

    const startUpload = vi.fn(
      (
        file: File,
        { onProgress }: { onProgress: (progress: { loaded: number; total: number | null; percent: number | null }) => void },
      ) => {
        onProgress({ loaded: 0, total: file.size, percent: 0 });
        const deferred = createDeferred<{ data: string | null; status: number }>();
        const abort = vi.fn();
        uploads.push({ deferred, abort });
        return { promise: deferred.promise, abort };
      },
    );

    const { result } = renderHook(() => useUploadQueue({ concurrency: 2, startUpload }));

    act(() => {
      result.current.enqueue([
        createFile("a.csv", 100),
        createFile("b.csv", 100),
        createFile("c.csv", 100),
      ]);
    });

    expect(startUpload).toHaveBeenCalledTimes(2);
    expect(result.current.items.filter((item) => item.status === "uploading")).toHaveLength(2);
    expect(result.current.items.filter((item) => item.status === "queued")).toHaveLength(1);

    await act(async () => {
      uploads[0].deferred.resolve({ data: "ok", status: 201 });
    });

    await waitFor(() => {
      expect(startUpload).toHaveBeenCalledTimes(3);
    });
  });

  it("retries failed uploads", async () => {
    const uploads: Array<Deferred<{ data: string | null; status: number }>> = [];
    const startUpload = vi.fn(() => {
      const attempt = createDeferred<{ data: string | null; status: number }>();
      uploads.push(attempt);
      return { promise: attempt.promise, abort: vi.fn() };
    });
    const { result } = renderHook(() => useUploadQueue({ concurrency: 1, startUpload }));

    act(() => {
      result.current.enqueue([createFile("fail.csv", 50)]);
    });

    await act(async () => {
      uploads[0].reject(new Error("Upload failed."));
    });

    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe("failed");
    });

    act(() => {
      result.current.retry(result.current.items[0].id);
    });

    await waitFor(() => {
      expect(startUpload).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe("uploading");
    });
  });

  it("cancels in-flight uploads", async () => {
    const deferred = createDeferred<{ data: string | null; status: number }>();
    const abort = vi.fn();
    const startUpload = vi.fn(() => ({ promise: deferred.promise, abort }));
    const { result } = renderHook(() => useUploadQueue({ concurrency: 1, startUpload }));

    act(() => {
      result.current.enqueue([createFile("cancel.csv", 20)]);
    });

    act(() => {
      result.current.cancel(result.current.items[0].id);
    });

    expect(abort).toHaveBeenCalled();
    await waitFor(() => {
      expect(result.current.items[0]?.status).toBe("cancelled");
    });
  });
});

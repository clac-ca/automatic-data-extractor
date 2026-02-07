import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RunResource } from "@/api/runs/api";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { useDocumentActivityFeed } from "./useDocumentActivityFeed";

const useSessionMock = vi.fn();
const useDocumentCommentsMock = vi.fn();
const fetchWorkspaceRunsForDocumentMock = vi.fn();

vi.mock("@/providers/auth/SessionContext", () => ({
  useSession: () => useSessionMock(),
}));

vi.mock(
  "@/pages/Workspace/sections/Documents/detail/tabs/comments/hooks/useDocumentComments",
  () => ({
    useDocumentComments: (...args: unknown[]) => useDocumentCommentsMock(...args),
  }),
);

vi.mock("@/api/runs/api", () => ({
  fetchWorkspaceRunsForDocument: (...args: unknown[]) =>
    fetchWorkspaceRunsForDocumentMock(...args),
}));

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolveFn) => {
    resolve = resolveFn;
  });
  return { promise, resolve };
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function makeDocument(): DocumentRow {
  return {
    id: "doc_1",
    workspaceId: "ws_1",
    name: "sample.xlsx",
    fileType: "xlsx",
    byteSize: 100,
    commentCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    tags: [],
    assignee: null,
    uploader: null,
    lastRun: null,
  } as DocumentRow;
}

describe("useDocumentActivityFeed", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("stays loading while runs are pending even when activity already has items", async () => {
    const runsDeferred = createDeferred<RunResource[]>();
    fetchWorkspaceRunsForDocumentMock.mockReturnValue(runsDeferred.promise);
    useSessionMock.mockReturnValue({
      user: {
        id: "user_1",
        display_name: "Ada User",
        email: "ada@example.com",
      },
    });
    useDocumentCommentsMock.mockReturnValue({
      comments: [],
      hasNextPage: false,
      isFetchingNextPage: false,
      isLoading: false,
      error: null,
      submitError: null,
      isSubmitting: false,
      submitComment: vi.fn().mockResolvedValue(undefined),
      fetchNextPage: vi.fn().mockResolvedValue(undefined),
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { result } = renderHook(
      () =>
        useDocumentActivityFeed({
          workspaceId: "ws_1",
          document: makeDocument(),
          filter: "all",
        }),
      { wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => {
      expect(fetchWorkspaceRunsForDocumentMock).toHaveBeenCalledTimes(1);
    });

    expect(result.current.visibleItems).toHaveLength(1);
    expect(result.current.isLoading).toBe(true);

    runsDeferred.resolve([]);
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

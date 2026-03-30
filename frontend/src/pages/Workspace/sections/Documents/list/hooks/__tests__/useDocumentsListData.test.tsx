import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as documentsApi from "@/api/documents";

import { useDocumentsListData } from "../useDocumentsListData";

function createRow(id: string, name: string) {
  return {
    id,
    workspaceId: "ws-1",
    name,
    fileType: "xlsx" as const,
    byteSize: 12,
    commentCount: 0,
    tags: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    assignee: null,
    uploader: null,
    lastRun: null,
    lastRunMetrics: null,
    lastRunTableColumns: null,
    lastRunFields: null,
  };
}

function createPage(id: string, totalCount: number | null) {
  return {
    items: [createRow(id, `${id}.xlsx`)],
    meta: {
      limit: 20,
      hasMore: false,
      nextCursor: null,
      totalIncluded: totalCount !== null,
      totalCount,
      changesCursor: null,
    },
    facets: null,
  };
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useDocumentsListData", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("caches totals by query signature and fetches later pages directly", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    const fetchSpy = vi
      .spyOn(documentsApi, "fetchWorkspaceDocuments")
      .mockResolvedValueOnce(createPage("doc-1", 3))
      .mockResolvedValueOnce(createPage("doc-2", null))
      .mockResolvedValueOnce(createPage("doc-2", 3));

    const { result, rerender } = renderHook(
      ({ page }) =>
        useDocumentsListData({
          workspaceId: "ws-1",
          page,
          perPage: 20,
          sort: null,
          q: null,
          lifecycle: "active",
          filters: null,
          joinOperator: null,
        }),
      {
        initialProps: { page: 1 },
        wrapper: createWrapper(queryClient),
      },
    );

    await waitFor(() => {
      expect(result.current.total).toBe(3);
    });
    expect(fetchSpy.mock.calls[0]?.[1]).toMatchObject({
      page: 1,
      limit: 20,
      includeTotal: true,
    });

    rerender({ page: 2 });

    await waitFor(() => {
      expect(result.current.rows[0]?.id).toBe("doc-2");
    });
    expect(fetchSpy.mock.calls[1]?.[1]).toMatchObject({
      page: 2,
      limit: 20,
      includeTotal: false,
    });
    expect(result.current.total).toBe(3);

    await act(async () => {
      await result.current.refreshSnapshot();
    });

    expect(fetchSpy.mock.calls[2]?.[1]).toMatchObject({
      page: 2,
      limit: 20,
      includeTotal: true,
    });
  });
});

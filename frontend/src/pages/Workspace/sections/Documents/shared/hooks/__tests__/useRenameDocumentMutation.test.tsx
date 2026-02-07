import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as documentsApi from "@/api/documents";
import { ApiError } from "@/api/errors";

import {
  getRenameDocumentErrorMessage,
  useRenameDocumentMutation,
} from "../useRenameDocumentMutation";

function createRow(name: string) {
  return {
    id: "doc-1",
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

function createPage(name: string) {
  return {
    items: [createRow(name)],
    meta: {
      limit: 50,
      hasMore: false,
      nextCursor: null,
      totalIncluded: false,
      totalCount: null,
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

describe("useRenameDocumentMutation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("updates list and detail cache entries through one shared mutation", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const listKey = ["documents", "ws-1", 1, 50] as const;
    const detailKey = ["documents-detail", "ws-1", "doc-1"] as const;
    queryClient.setQueryData(listKey, createPage("source.xlsx"));
    queryClient.setQueryData(detailKey, createRow("source.xlsx"));

    vi.spyOn(documentsApi, "patchWorkspaceDocument").mockResolvedValue({
      id: "doc-1",
      workspaceId: "ws-1",
      name: "renamed.xlsx",
      byteSize: 12,
      commentCount: 0,
      tags: [],
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-02T00:00:00Z",
      activityAt: "2026-01-02T00:00:00Z",
      listRow: {
        ...createRow("renamed.xlsx"),
        updatedAt: "2026-01-02T00:00:00Z",
        activityAt: "2026-01-02T00:00:00Z",
      },
    } as Awaited<ReturnType<typeof documentsApi.patchWorkspaceDocument>>);

    const { result } = renderHook(
      () => useRenameDocumentMutation({ workspaceId: "ws-1" }),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await result.current.renameDocument({
        documentId: "doc-1",
        currentName: "source.xlsx",
        nextName: "renamed.xlsx",
      });
    });

    const listPage = queryClient.getQueryData<ReturnType<typeof createPage>>(listKey);
    const detailRow = queryClient.getQueryData<ReturnType<typeof createRow>>(detailKey);

    expect(listPage?.items[0]?.name).toBe("renamed.xlsx");
    expect(detailRow?.name).toBe("renamed.xlsx");
  });

  it("restores optimistic cache updates when rename fails", async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    const listKey = ["documents", "ws-1", 1, 50] as const;
    const detailKey = ["documents-detail", "ws-1", "doc-1"] as const;
    queryClient.setQueryData(listKey, createPage("source.xlsx"));
    queryClient.setQueryData(detailKey, createRow("source.xlsx"));

    vi.spyOn(documentsApi, "patchWorkspaceDocument").mockRejectedValue(
      new ApiError("duplicate", 409),
    );

    const { result } = renderHook(
      () => useRenameDocumentMutation({ workspaceId: "ws-1" }),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await expect(
        result.current.renameDocument({
          documentId: "doc-1",
          currentName: "source.xlsx",
          nextName: "conflict.xlsx",
        }),
      ).rejects.toBeInstanceOf(ApiError);
    });

    const listPage = queryClient.getQueryData<ReturnType<typeof createPage>>(listKey);
    const detailRow = queryClient.getQueryData<ReturnType<typeof createRow>>(detailKey);

    expect(listPage?.items[0]?.name).toBe("source.xlsx");
    expect(detailRow?.name).toBe("source.xlsx");
  });
});

describe("getRenameDocumentErrorMessage", () => {
  it("maps known API status codes to user-friendly messages", () => {
    expect(getRenameDocumentErrorMessage(new ApiError("Conflict", 409))).toBe(
      "A document with this name already exists.",
    );
    expect(getRenameDocumentErrorMessage(new ApiError("Invalid", 422))).toBe(
      "File extension cannot be changed.",
    );
  });

  it("falls back to raw messages for unknown failures", () => {
    expect(getRenameDocumentErrorMessage(new Error("unexpected"))).toBe("unexpected");
  });
});

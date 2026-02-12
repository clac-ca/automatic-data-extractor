import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as documentsApi from "@/api/documents";
import * as runsApi from "@/api/runs/api";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import type { PreviewDisplayPreferences } from "../../model";
import { useDocumentPreviewModel } from "../useDocumentPreviewModel";

function createDocument(): DocumentRow {
  return {
    id: "doc-1",
    workspaceId: "ws-1",
    name: "example.xlsx",
    fileType: "xlsx",
    byteSize: 20,
    commentCount: 0,
    tags: [],
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    lastRun: null,
    lastRunMetrics: null,
    lastRunTableColumns: null,
    lastRunFields: null,
  } as DocumentRow;
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
        refetchOnWindowFocus: false,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function buildPreferences(enabled: boolean): PreviewDisplayPreferences {
  return {
    trimEmptyRows: enabled,
    trimEmptyColumns: enabled,
  };
}

describe("useDocumentPreviewModel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("passes compact preferences to document preview requests", async () => {
    const fetchDocumentSheetsSpy = vi
      .spyOn(documentsApi, "fetchDocumentSheets")
      .mockResolvedValue([{ name: "Sheet A", index: 0, kind: "worksheet", is_active: true }]);
    const fetchDocumentPreviewSpy = vi.spyOn(documentsApi, "fetchDocumentPreview").mockResolvedValue({
      name: "Sheet A",
      index: 0,
      rows: [["A1"]],
      totalRows: 1,
      totalColumns: 1,
      truncatedRows: false,
      truncatedColumns: false,
    });

    vi.spyOn(runsApi, "fetchRunOutputSheets").mockResolvedValue([]);
    vi.spyOn(runsApi, "fetchRunOutputPreview").mockResolvedValue({
      name: "Sheet A",
      index: 0,
      rows: [],
      totalRows: 0,
      totalColumns: 0,
      truncatedRows: false,
      truncatedColumns: false,
    });

    const onSheetChange = vi.fn();
    const wrapper = createWrapper();

    const { rerender } = renderHook(
      (props: { displayPreferences: PreviewDisplayPreferences }) =>
        useDocumentPreviewModel({
          workspaceId: "ws-1",
          document: createDocument(),
          source: "original",
          sheet: null,
          onSheetChange,
          displayPreferences: props.displayPreferences,
        }),
      {
        wrapper,
        initialProps: { displayPreferences: buildPreferences(true) },
      },
    );

    await waitFor(() => {
      expect(fetchDocumentSheetsSpy).toHaveBeenCalled();
      const latestCall = fetchDocumentPreviewSpy.mock.calls.at(-1);
      expect(latestCall?.[0]).toBe("ws-1");
      expect(latestCall?.[1]).toBe("doc-1");
      expect(latestCall?.[2]).toEqual(
        expect.objectContaining({
          trimEmptyRows: true,
          trimEmptyColumns: true,
        }),
      );
    });

    rerender({ displayPreferences: buildPreferences(false) });

    await waitFor(() => {
      const latestCall = fetchDocumentPreviewSpy.mock.calls.at(-1);
      expect(latestCall?.[0]).toBe("ws-1");
      expect(latestCall?.[1]).toBe("doc-1");
      expect(latestCall?.[2]).toEqual(
        expect.objectContaining({
          trimEmptyRows: false,
          trimEmptyColumns: false,
        }),
      );
    });
  });

  it("builds explicit visible-vs-total summary labels for reduced previews", async () => {
    vi.spyOn(documentsApi, "fetchDocumentSheets").mockResolvedValue([
      { name: "Sheet A", index: 0, kind: "worksheet", is_active: true },
    ]);
    vi.spyOn(documentsApi, "fetchDocumentPreview").mockResolvedValue({
      name: "Sheet A",
      index: 0,
      rows: [["A1", "B1"], ["A2", "B2"]],
      totalRows: 10,
      totalColumns: 8,
      truncatedRows: true,
      truncatedColumns: true,
    });

    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useDocumentPreviewModel({
          workspaceId: "ws-1",
          document: createDocument(),
          source: "original",
          sheet: null,
          onSheetChange: vi.fn(),
          displayPreferences: buildPreferences(true),
        }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.previewCountSummary?.rowsVisibleLabel).toBe("Showing 2 of 10 rows");
      expect(result.current.previewCountSummary?.columnsVisibleLabel).toBe("Showing 2 of 8 columns");
      expect(result.current.columnLabels).toHaveLength(2);
    });
  });

  it("derives visible column summary from preview width when labels are expanded", async () => {
    vi.spyOn(documentsApi, "fetchDocumentSheets").mockResolvedValue([
      { name: "Sheet A", index: 0, kind: "worksheet", is_active: true },
    ]);
    vi.spyOn(documentsApi, "fetchDocumentPreview").mockResolvedValue({
      name: "Sheet A",
      index: 0,
      rows: [Array.from({ length: 50 }, (_, index) => `C${index + 1}`)],
      totalRows: 1,
      totalColumns: 102,
      truncatedRows: false,
      truncatedColumns: true,
    });

    const wrapper = createWrapper();

    const { result } = renderHook(
      () =>
        useDocumentPreviewModel({
          workspaceId: "ws-1",
          document: createDocument(),
          source: "original",
          sheet: null,
          onSheetChange: vi.fn(),
          displayPreferences: buildPreferences(false),
        }),
      { wrapper },
    );

    await waitFor(() => {
      expect(result.current.previewCountSummary?.columnsVisibleLabel).toBe(
        "Showing 50 of 102 columns",
      );
      expect(result.current.columnLabels).toHaveLength(102);
    });
  });
});

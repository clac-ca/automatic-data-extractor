import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { uiStorageKeys } from "@/lib/uiStorageKeys";

import { usePreviewDisplayPreferences } from "../usePreviewDisplayPreferences";

describe("usePreviewDisplayPreferences", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to showing the full worksheet surface while hiding Excel-hidden rows and columns", () => {
    const { result } = renderHook(() => usePreviewDisplayPreferences("ws-1"));

    expect(result.current.preferences).toEqual({
      trimEmptyRows: false,
      trimEmptyColumns: false,
      showHiddenRowsAndColumns: false,
    });
    expect(result.current.showHiddenRowsAndColumns).toBe(false);
  });

  it("persists hidden row and column visibility to workspace-scoped storage", async () => {
    const { result, unmount } = renderHook(() => usePreviewDisplayPreferences("ws-1"));

    act(() => {
      result.current.setShowHiddenRowsAndColumns(true);
    });

    await waitFor(() => {
      expect(window.localStorage.getItem(uiStorageKeys.documentsDetailPreviewDisplay("ws-1"))).toBe(
        JSON.stringify({
          trimEmptyRows: false,
          trimEmptyColumns: false,
          showHiddenRowsAndColumns: true,
        }),
      );
    });

    unmount();

    const next = renderHook(() => usePreviewDisplayPreferences("ws-1"));
    expect(next.result.current.preferences).toEqual({
      trimEmptyRows: false,
      trimEmptyColumns: false,
      showHiddenRowsAndColumns: true,
    });
    expect(next.result.current.showHiddenRowsAndColumns).toBe(true);
  });

  it("isolates preferences by workspace id", async () => {
    const ws1 = renderHook(() => usePreviewDisplayPreferences("ws-1"));
    const ws2 = renderHook(() => usePreviewDisplayPreferences("ws-2"));

    act(() => {
      ws1.result.current.setShowHiddenRowsAndColumns(true);
    });

    await waitFor(() => {
      expect(ws1.result.current.showHiddenRowsAndColumns).toBe(true);
    });

    expect(ws2.result.current.showHiddenRowsAndColumns).toBe(false);
  });
});

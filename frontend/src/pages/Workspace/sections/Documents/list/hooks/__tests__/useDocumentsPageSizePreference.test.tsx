import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { uiStorageKeys } from "@/lib/uiStorageKeys";

import { useDocumentsPageSizePreference } from "../useDocumentsPageSizePreference";

describe("useDocumentsPageSizePreference", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to 100 rows when no preference is stored", () => {
    const { result } = renderHook(() => useDocumentsPageSizePreference("ws-1"));

    expect(result.current.defaultPageSize).toBe(100);
  });

  it("persists supported page sizes to workspace-scoped storage", async () => {
    const { result, unmount } = renderHook(() => useDocumentsPageSizePreference("ws-1"));

    act(() => {
      result.current.setPageSizePreference(500);
    });

    await waitFor(() => {
      expect(window.localStorage.getItem(uiStorageKeys.documentsRowsPerPage("ws-1"))).toBe(
        JSON.stringify(500),
      );
    });

    unmount();

    const next = renderHook(() => useDocumentsPageSizePreference("ws-1"));
    expect(next.result.current.defaultPageSize).toBe(500);
  });

  it("falls back to 100 when the stored value is invalid", () => {
    window.localStorage.setItem(
      uiStorageKeys.documentsRowsPerPage("ws-1"),
      JSON.stringify(999),
    );

    const { result } = renderHook(() => useDocumentsPageSizePreference("ws-1"));

    expect(result.current.defaultPageSize).toBe(100);
  });

  it("isolates page size preferences by workspace id", async () => {
    const ws1 = renderHook(() => useDocumentsPageSizePreference("ws-1"));
    const ws2 = renderHook(() => useDocumentsPageSizePreference("ws-2"));

    act(() => {
      ws1.result.current.setPageSizePreference(1000);
    });

    await waitFor(() => {
      expect(ws1.result.current.defaultPageSize).toBe(1000);
    });

    expect(ws2.result.current.defaultPageSize).toBe(100);
  });
});

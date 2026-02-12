import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { uiStorageKeys } from "@/lib/uiStorageKeys";

import { usePreviewDisplayPreferences } from "../usePreviewDisplayPreferences";

describe("usePreviewDisplayPreferences", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to compact mode when no preference is stored", () => {
    const { result } = renderHook(() => usePreviewDisplayPreferences("ws-1"));

    expect(result.current.preferences).toEqual({
      trimEmptyRows: true,
      trimEmptyColumns: true,
    });
    expect(result.current.isCompactMode).toBe(true);
  });

  it("persists compact mode changes to workspace-scoped storage", async () => {
    const { result, unmount } = renderHook(() => usePreviewDisplayPreferences("ws-1"));

    act(() => {
      result.current.setCompactMode(false);
    });

    await waitFor(() => {
      expect(window.localStorage.getItem(uiStorageKeys.documentsDetailPreviewDisplay("ws-1"))).toBe(
        JSON.stringify({
          trimEmptyRows: false,
          trimEmptyColumns: false,
        }),
      );
    });

    unmount();

    const next = renderHook(() => usePreviewDisplayPreferences("ws-1"));
    expect(next.result.current.preferences).toEqual({
      trimEmptyRows: false,
      trimEmptyColumns: false,
    });
    expect(next.result.current.isCompactMode).toBe(false);
  });

  it("isolates preferences by workspace id", async () => {
    const ws1 = renderHook(() => usePreviewDisplayPreferences("ws-1"));
    const ws2 = renderHook(() => usePreviewDisplayPreferences("ws-2"));

    act(() => {
      ws1.result.current.setCompactMode(false);
    });

    await waitFor(() => {
      expect(ws1.result.current.isCompactMode).toBe(false);
    });

    expect(ws2.result.current.isCompactMode).toBe(true);
  });
});

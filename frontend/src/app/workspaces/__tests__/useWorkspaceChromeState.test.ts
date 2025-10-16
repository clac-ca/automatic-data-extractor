import { describe, expect, it, beforeEach } from "vitest";

import { act, renderHook, waitFor } from "../../../test/test-utils";
import { useWorkspaceChromeState } from "../useWorkspaceChromeState";

const storageKey = (workspaceId: string) => `ade.workspace.${workspaceId}.chrome_state`;

describe("useWorkspaceChromeState", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("hydrates persisted state for nav collapse and focus mode", async () => {
    const key = storageKey("workspace-123");
    window.localStorage.setItem(
      key,
      JSON.stringify({
        navCollapsed: true,
        focusMode: true,
      }),
    );

    const { result } = renderHook(() => useWorkspaceChromeState("workspace-123"));

    await waitFor(() => {
      expect(result.current.isNavCollapsed).toBe(true);
      expect(result.current.isFocusMode).toBe(true);
    });
  });

  it("toggles nav collapse state and persists it", () => {
    const { result } = renderHook(() => useWorkspaceChromeState("workspace-456"));

    expect(result.current.isNavCollapsed).toBe(false);

    act(() => {
      result.current.toggleNavCollapsed();
    });

    expect(result.current.isNavCollapsed).toBe(true);
    const stored = JSON.parse(window.localStorage.getItem(storageKey("workspace-456")) ?? "{}");
    expect(stored.navCollapsed).toBe(true);
  });

  it("toggles focus mode and persists it", () => {
    const { result } = renderHook(() => useWorkspaceChromeState("workspace-789"));

    expect(result.current.isFocusMode).toBe(false);

    act(() => {
      result.current.toggleFocusMode();
    });

    expect(result.current.isFocusMode).toBe(true);
    const stored = JSON.parse(window.localStorage.getItem(storageKey("workspace-789")) ?? "{}");
    expect(stored.focusMode).toBe(true);
  });
});

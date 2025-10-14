import { describe, expect, it, beforeEach } from "vitest";

import { act, renderHook, waitFor } from "../../../test/test-utils";
import { useWorkspaceRailState } from "../useWorkspaceRailState";

const storageKey = (workspaceId: string) => `ade.workspace.${workspaceId}.rail_state`;

describe("useWorkspaceRailState", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("hydrates state from local storage when available", async () => {
    const key = storageKey("workspace-123");
    window.localStorage.setItem(
      key,
      JSON.stringify({
        pinned: ["doc-1", "doc-2"],
        collapsed: true,
      }),
    );

    const { result } = renderHook(() => useWorkspaceRailState("workspace-123"));

    await waitFor(() => {
      expect(result.current.isCollapsed).toBe(true);
      expect(result.current.pinnedDocumentIds).toEqual(["doc-1", "doc-2"]);
    });
  });

  it("toggles the collapsed state and persists it", () => {
    const { result } = renderHook(() => useWorkspaceRailState("workspace-456"));

    expect(result.current.isCollapsed).toBe(false);

    act(() => {
      result.current.toggleCollapse();
    });

    expect(result.current.isCollapsed).toBe(true);
    const stored = JSON.parse(
      window.localStorage.getItem(storageKey("workspace-456")) ?? "{}",
    );
    expect(stored.collapsed).toBe(true);
  });

  it("adds and removes pinned document ids without duplicates", () => {
    const { result } = renderHook(() => useWorkspaceRailState("workspace-789"));

    act(() => {
      result.current.setPinned("doc-1", true);
      result.current.setPinned("doc-1", true);
      result.current.setPinned("doc-2", true);
    });

    expect(result.current.pinnedDocumentIds).toEqual(["doc-1", "doc-2"]);

    act(() => {
      result.current.setPinned("doc-1", false);
    });

    expect(result.current.pinnedDocumentIds).toEqual(["doc-2"]);
    const stored = JSON.parse(
      window.localStorage.getItem(storageKey("workspace-789")) ?? "{}",
    );
    expect(stored.pinned).toEqual(["doc-2"]);
  });
});

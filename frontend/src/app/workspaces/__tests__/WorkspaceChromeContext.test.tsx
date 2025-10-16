import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { act, renderHook } from "../../../test/test-utils";
import { WorkspaceChromeProvider, useWorkspaceChrome } from "../WorkspaceChromeContext";

function wrapper({ children }: { readonly children: ReactNode }) {
  return (
    <WorkspaceChromeProvider
      isNavCollapsed={false}
      toggleNavCollapsed={() => undefined}
      setNavCollapsed={() => undefined}
      isSectionCollapsed={false}
      toggleSectionCollapsed={() => undefined}
      setSectionCollapsed={() => undefined}
      isFocusMode={false}
      toggleFocusMode={() => undefined}
      setFocusMode={() => undefined}
    >
      {children}
    </WorkspaceChromeProvider>
  );
}

describe("WorkspaceChromeContext", () => {
  it("runs cleanup when the inspector closes", () => {
    const cleanup = vi.fn();

    const { result } = renderHook(() => useWorkspaceChrome(), { wrapper });

    act(() => {
      result.current.openInspector({
        title: "Test",
        content: <div>Test</div>,
        onClose: cleanup,
      });
    });

    expect(result.current.inspector.isOpen).toBe(true);

    act(() => {
      result.current.closeInspector();
    });

    expect(result.current.inspector.isOpen).toBe(false);
    expect(cleanup).toHaveBeenCalledTimes(1);
  });
});

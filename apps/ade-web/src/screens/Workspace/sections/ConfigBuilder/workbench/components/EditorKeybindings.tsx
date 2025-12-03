import { useEffect, type RefObject } from "react";

import type { WorkbenchFileTab } from "../types";

interface EditorKeybindingsProps {
  readonly containerRef: RefObject<HTMLElement | null>;
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onCloseTab: (tabId: string) => void;
  readonly onSelectRecentTab: (direction: "forward" | "backward") => void;
  readonly onSelectTab: (tabId: string) => void;
}

export function EditorKeybindings({
  containerRef,
  tabs,
  activeTabId,
  onCloseTab,
  onSelectRecentTab,
  onSelectTab,
}: EditorKeybindingsProps) {
  useEffect(() => {
    if (!tabs.length) {
      return;
    }

    const shouldHandleEvent = (event: KeyboardEvent) => {
      const scope = containerRef.current;
      if (!scope) {
        return false;
      }
      const targetNode = event.target;
      if (targetNode instanceof Node && scope.contains(targetNode)) {
        return true;
      }
      const activeElement = document.activeElement;
      return Boolean(activeElement && scope.contains(activeElement));
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }
      if (!shouldHandleEvent(event)) {
        return;
      }

      if (event.key.toLowerCase() === "w") {
        if (!activeTabId) {
          return;
        }
        event.preventDefault();
        onCloseTab(activeTabId);
        return;
      }

      if (event.key === "Tab") {
        if (tabs.length < 2) {
          return;
        }
        event.preventDefault();
        onSelectRecentTab(event.shiftKey ? "backward" : "forward");
        return;
      }

      const cycleVisual = (delta: number) => {
        if (tabs.length < 2) {
          return;
        }
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTabId);
        const safeIndex = currentIndex >= 0 ? currentIndex : 0;
        const nextIndex = (safeIndex + delta + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          onSelectTab(nextTab.id);
        }
      };

      if (event.key === "PageUp") {
        event.preventDefault();
        cycleVisual(-1);
        return;
      }

      if (event.key === "PageDown") {
        event.preventDefault();
        cycleVisual(1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [tabs, activeTabId, onCloseTab, onSelectRecentTab, onSelectTab, containerRef]);

  return null;
}

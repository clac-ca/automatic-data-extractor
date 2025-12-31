import { useMemo, useRef, useState } from "react";

import { TabsRoot } from "@components/ui/tabs";

import type { WorkbenchFileTab } from "../types";
import { EditorKeybindings } from "./EditorKeybindings";
import { EditorPane } from "./EditorPane";
import { EditorTabStrip } from "./EditorTabStrip";

interface EditorAreaProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onCloseOtherTabs: (tabId: string) => void;
  readonly onCloseTabsToRight: (tabId: string) => void;
  readonly onCloseAllTabs: () => void;
  readonly onMoveTab: (tabId: string, targetIndex: number) => void;
  readonly onPinTab: (tabId: string) => void;
  readonly onUnpinTab: (tabId: string) => void;
  readonly onContentChange: (tabId: string, value: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly onSaveAllTabs?: () => void;
  readonly onSelectRecentTab: (direction: "forward" | "backward") => void;
  readonly editorTheme: string;
  readonly menuAppearance: "light" | "dark";
  readonly canSaveFiles?: boolean;
  readonly readOnly?: boolean;
  readonly minHeight?: number;
  readonly onRetryTabLoad?: (tabId: string) => void;
}

export function EditorArea({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onCloseOtherTabs,
  onCloseTabsToRight,
  onCloseAllTabs,
  onMoveTab,
  onPinTab,
  onUnpinTab,
  onContentChange,
  onSaveTab,
  onSaveAllTabs,
  onSelectRecentTab,
  editorTheme,
  menuAppearance,
  canSaveFiles = false,
  readOnly = false,
  minHeight,
  onRetryTabLoad,
}: EditorAreaProps) {
  const hasTabs = tabs.length > 0;
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [isTabDragging, setIsTabDragging] = useState(false);

  const activeTab = useMemo(() => tabs.find((tab) => tab.id === activeTabId) ?? null, [tabs, activeTabId]);

  if (!hasTabs || !activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div
      ref={rootRef}
      className="flex min-h-0 min-w-0 flex-1 flex-col"
      style={minHeight ? { minHeight } : undefined}
      data-editor-area
    >
      <EditorKeybindings
        containerRef={rootRef}
        tabs={tabs}
        activeTabId={activeTabId}
        onCloseTab={onCloseTab}
        onSelectTab={onSelectTab}
        onSelectRecentTab={onSelectRecentTab}
      />
      <TabsRoot value={activeTab.id} onValueChange={onSelectTab}>
        <EditorTabStrip
          tabs={tabs}
          activeTabId={activeTab.id}
          menuAppearance={menuAppearance}
          canSaveFiles={canSaveFiles}
          onSelectTab={onSelectTab}
          onCloseTab={onCloseTab}
          onCloseOtherTabs={onCloseOtherTabs}
          onCloseTabsToRight={onCloseTabsToRight}
          onCloseAllTabs={onCloseAllTabs}
          onMoveTab={onMoveTab}
          onPinTab={onPinTab}
          onUnpinTab={onUnpinTab}
          onSaveTab={onSaveTab}
          onSaveAllTabs={onSaveAllTabs}
          onTabDragStateChange={setIsTabDragging}
        />
        <EditorPane
          tabs={tabs}
          activeTabId={activeTab.id}
          editorTheme={editorTheme}
          onContentChange={onContentChange}
          onSaveTab={onSaveTab}
          canSaveFiles={canSaveFiles}
          readOnly={readOnly}
          onRetryTabLoad={onRetryTabLoad}
          onSelectTab={onSelectTab}
          isTabDragging={isTabDragging}
        />
      </TabsRoot>
    </div>
  );
}

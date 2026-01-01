import { useMemo } from "react";

import clsx from "clsx";

import { TabsContent } from "@/components/ui/tabs";

import type { WorkbenchFileTab } from "../types";
import { CodeEditor } from "./code-editor";

interface EditorPaneProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly editorTheme: string;
  readonly onContentChange: (tabId: string, value: string) => void;
  readonly onSaveTab?: (tabId: string) => void;
  readonly canSaveFiles?: boolean;
  readonly readOnly?: boolean;
  readonly onRetryTabLoad?: (tabId: string) => void;
  readonly onSelectTab: (tabId: string) => void;
  readonly isTabDragging?: boolean;
}

export function EditorPane({
  tabs,
  activeTabId,
  editorTheme,
  onContentChange,
  onSaveTab,
  canSaveFiles = false,
  readOnly = false,
  onRetryTabLoad,
  onSelectTab,
  isTabDragging = false,
}: EditorPaneProps) {
  const activeTab = useMemo(() => tabs.find((tab) => tab.id === activeTabId) ?? null, [tabs, activeTabId]);

  if (!activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      {tabs.map((tab) => (
        <TabsContent key={tab.id} value={tab.id} className="flex min-h-0 min-w-0 flex-1">
          {tab.status === "loading" ? (
            <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
              Loading {tab.name}…
            </div>
          ) : tab.status === "error" ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-sm text-muted-foreground">
              <p>{tab.error ?? "Unable to load the file."}</p>
              <button
                type="button"
                className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-on-brand hover:bg-brand-500"
                onClick={() => (onRetryTabLoad ? onRetryTabLoad(tab.id) : onSelectTab(tab.id))}
              >
                Retry loading
              </button>
            </div>
          ) : (
            <div
              className={clsx(
                "flex min-h-0 min-w-0 flex-1",
                isTabDragging && "pointer-events-none select-none",
              )}
            >
              <CodeEditor
                value={tab.content}
                language={tab.language ?? "plaintext"}
                path={tab.id}
                theme={editorTheme}
                readOnly={readOnly}
                onChange={(value) => onContentChange(tab.id, value ?? "")}
                onSaveShortcut={() => {
                  if (!canSaveFiles) {
                    return;
                  }
                  onSaveTab?.(tab.id);
                }}
              />
            </div>
          )}
        </TabsContent>
      ))}
    </div>
  );
}

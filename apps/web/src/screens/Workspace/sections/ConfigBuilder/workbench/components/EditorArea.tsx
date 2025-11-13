import { useEffect, useMemo } from "react";

import { CodeEditor } from "@ui/CodeEditor";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@ui/Tabs";

import type { WorkbenchFileTab } from "../types";

interface EditorAreaProps {
  readonly tabs: readonly WorkbenchFileTab[];
  readonly activeTabId: string;
  readonly onSelectTab: (tabId: string) => void;
  readonly onCloseTab: (tabId: string) => void;
  readonly onContentChange: (tabId: string, value: string) => void;
}

export function EditorArea({
  tabs,
  activeTabId,
  onSelectTab,
  onCloseTab,
  onContentChange,
}: EditorAreaProps) {
  const hasTabs = tabs.length > 0;

  const activeTab = useMemo(() => tabs.find((tab) => tab.id === activeTabId) ?? tabs[0], [tabs, activeTabId]);

  useEffect(() => {
    if (!hasTabs) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
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
        const currentIndex = tabs.findIndex((tab) => tab.id === activeTabId);
        const safeIndex = currentIndex >= 0 ? currentIndex : 0;
        const delta = event.shiftKey ? -1 : 1;
        const nextIndex = (safeIndex + delta + tabs.length) % tabs.length;
        const nextTab = tabs[nextIndex];
        if (nextTab) {
          onSelectTab(nextTab.id);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [hasTabs, tabs, activeTabId, onCloseTab, onSelectTab]);

  if (!hasTabs || !activeTab) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
        Select a file from the explorer to begin editing.
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <TabsRoot value={activeTab.id} onValueChange={onSelectTab}>
        <TabsList className="flex items-center gap-1 border-b border-slate-200 px-2 py-1">
          {tabs.map((tab) => {
            const isDirty = tab.status === "ready" && tab.content !== tab.initialContent;
            return (
              <div key={tab.id} className="relative">
                <TabsTrigger value={tab.id} className="flex items-center gap-2 rounded px-3 py-1 pr-6 text-sm">
                  <span>{tab.name}</span>
                  {tab.status === "loading" ? (
                    <span className="text-xs text-slate-400" aria-label="Loading">
                      ●
                    </span>
                  ) : null}
                  {tab.status === "error" ? (
                    <span className="text-xs text-danger-600" aria-label="Load failed">
                      !
                    </span>
                  ) : null}
                  {isDirty ? <span className="text-xs text-brand-600">●</span> : null}
                </TabsTrigger>
                <button
                  type="button"
                  className="absolute right-1 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
                  onClick={(event) => {
                    event.stopPropagation();
                    onCloseTab(tab.id);
                  }}
                  aria-label={`Close ${tab.name}`}
                >
                  ×
                </button>
              </div>
            );
          })}
        </TabsList>
        {tabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id} className="flex min-h-0 flex-1">
            {tab.status === "loading" ? (
              <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
                Loading {tab.name}…
              </div>
            ) : tab.status === "error" ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-sm text-slate-500">
                <p>{tab.error ?? "Unable to load the file."}</p>
                <button
                  type="button"
                  className="rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-500"
                  onClick={() => onSelectTab(tab.id)}
                >
                  Retry loading
                </button>
              </div>
            ) : (
              <CodeEditor
                value={tab.content}
                language={tab.language ?? "plaintext"}
                onChange={(value) => onContentChange(tab.id, value ?? "")}
              />
            )}
          </TabsContent>
        ))}
      </TabsRoot>
    </div>
  );
}

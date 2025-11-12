import { useMemo } from "react";

import { Button } from "@ui/button";
import { CodeEditor } from "@ui/code-editor";

import type { ViewMode } from "../hooks/useLocalPrefs";
import { EmptyState } from "./EmptyState";
import type { EditorTabState } from "../state/editorStore";
import { isTabDirty } from "../state/editorStore";

interface EditorSurfaceProps {
  readonly tabs: readonly EditorTabState[];
  readonly activeTab: EditorTabState | null;
  readonly onSelectTab: (path: string) => void;
  readonly onCloseTab: (path: string) => void;
  readonly onUpdateContent: (path: string, content: string) => void;
  readonly onSave: () => void;
  readonly onRun: () => void;
  readonly onValidate: () => void;
  readonly viewMode: ViewMode;
  readonly onChangeView: (next: ViewMode) => void;
  readonly isSaving: boolean;
  readonly dirty: boolean;
}

export function EditorSurface({
  tabs,
  activeTab,
  onSelectTab,
  onCloseTab,
  onUpdateContent,
  onSave,
  onRun,
  onValidate,
  viewMode,
  onChangeView,
  isSaving,
  dirty,
}: EditorSurfaceProps) {
  const splitMode = viewMode === "split";
  const zenMode = viewMode === "zen";

  const previewContent = useMemo(() => {
    if (!activeTab) {
      return "";
    }
    if (activeTab.mime === "application/json") {
      try {
        return JSON.stringify(JSON.parse(activeTab.content), null, 2);
      } catch {
        return activeTab.content;
      }
    }
    return activeTab.content;
  }, [activeTab]);

  const handleFormat = () => {
    if (!activeTab) {
      return;
    }
    if (activeTab.mime === "application/json") {
      try {
        const formatted = JSON.stringify(JSON.parse(activeTab.content), null, 2);
        onUpdateContent(activeTab.path, formatted);
      } catch {
        // ignore formatting errors for now
      }
    }
  };

  const renderTabs = () => {
    if (tabs.length === 0) {
      return null;
    }
    return (
      <div className="flex items-center gap-2 overflow-x-auto">
        {tabs.map((tab) => {
          const active = tab.path === activeTab?.path;
          return (
            <div
              key={tab.path}
              className={`flex items-center gap-2 rounded-xl px-3 py-1 text-xs ${
                active ? "bg-slate-900/80 text-white" : "bg-slate-800/60 text-slate-300"
              }`}
            >
              <button type="button" onClick={() => onSelectTab(tab.path)} className="truncate font-medium">
                {tab.name}
                {isTabDirty(tab) ? " •" : ""}
              </button>
              <button
                type="button"
                onClick={() => onCloseTab(tab.path)}
                className="rounded-full px-1 text-slate-400 hover:bg-slate-700 hover:text-white"
                aria-label={`Close ${tab.name}`}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className={`flex h-full flex-col rounded-2xl border border-slate-800/40 bg-slate-950/80 shadow-xl ${zenMode ? "zen" : ""}`}>
      <header className="flex flex-col gap-3 border-b border-slate-800/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            <span>Editor</span>
            {dirty ? <span className="text-amber-400">Unsaved</span> : <span className="text-slate-500">Saved</span>}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={onSave} isLoading={isSaving} disabled={!activeTab}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={handleFormat} disabled={!activeTab || activeTab.mime !== "application/json"}>
              Format
            </Button>
            <Button size="sm" variant="ghost" onClick={onRun} disabled={!activeTab}>
              Run
            </Button>
            <Button size="sm" variant="ghost" onClick={onValidate} disabled={!activeTab}>
              Validate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onChangeView(splitMode ? "editor" : "split")}
              aria-pressed={splitMode}
            >
              Split
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onChangeView(zenMode ? "editor" : "zen")}
              aria-pressed={zenMode}
            >
              Zen
            </Button>
          </div>
        </div>
        {renderTabs()}
      </header>
      <div className="flex min-h-0 flex-1 flex-col">
        {!activeTab ? (
          <div className="flex flex-1 items-center justify-center p-10">
            <EmptyState title="Open a file" description="Select a file from the explorer or use ⌘P to quick open." />
          </div>
        ) : (
          <div className={`flex flex-1 ${splitMode ? "flex-row" : "flex-col"}`}>
            <div className={`flex-1 ${splitMode ? "basis-1/2" : "basis-full"}`}>
              <CodeEditor
                key={activeTab.path}
                value={activeTab.content}
                onChange={(value) => onUpdateContent(activeTab.path, value)}
                language={activeTab.language}
                onSaveShortcut={onSave}
                readOnly={activeTab.isLoading}
                className="h-full"
              />
            </div>
            {splitMode ? (
              <div className="hidden h-full basis-1/2 border-l border-slate-800/60 bg-slate-950/80 text-left text-xs text-slate-400 md:block">
                <pre className="h-full overflow-auto p-4 text-[13px] leading-relaxed text-slate-200">
                  <code>{previewContent}</code>
                </pre>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { useSearchParams } from "react-router";

import { Button } from "@ui/button";

import type { ConfigFsAdapter } from "../adapters/ConfigFsAdapter";
import type { FileNode, Problem } from "../adapters/types";
import { CommandPalette } from "./CommandPalette";
import { ConsolePanel } from "./ConsolePanel";
import { EditorSurface } from "./EditorSurface";
import { ExplorerTree } from "./ExplorerTree";
import { TopBar } from "./TopBar";
import { useEditorState } from "../hooks/useEditorState";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useLocalPrefs, type ViewMode } from "../hooks/useLocalPrefs";

interface WorkbenchProps {
  readonly adapter: ConfigFsAdapter;
  readonly storageKey: string;
}

export function Workbench({ adapter, storageKey }: WorkbenchProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const { prefs, updatePrefs } = useLocalPrefs(storageKey);

  const [tree, setTree] = useState<FileNode[]>([]);
  const [treeLoading, setTreeLoading] = useState<boolean>(false);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [isExplorerResizing, setExplorerResizing] = useState(false);
  const layoutRef = useRef<HTMLDivElement>(null);
  const [consoleHeight, setConsoleHeight] = useState(prefs.consoleHeight);
  const [isConsoleOpen, setConsoleOpen] = useState(() => {
    const param = searchParams.get("console");
    if (!param) {
      return prefs.consoleOpen;
    }
    return param === "open";
  });
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const param = searchParams.get("view");
    if (param === "split" || param === "zen" || param === "editor") {
      return param;
    }
    return prefs.viewMode;
  });
  const [explorerWidth, setExplorerWidth] = useState(prefs.explorerWidth);

  const updateSearch = useCallback(
    (updater: (params: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams);
      updater(next);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const refreshTree = useCallback(async () => {
    setTreeLoading(true);
    try {
      const nodes = await adapter.listTree();
      setTree(nodes);
      setTreeError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to load file tree.";
      setTreeError(message);
    } finally {
      setTreeLoading(false);
    }
  }, [adapter]);

  useEffect(() => {
    void refreshTree();
  }, [refreshTree]);

  useEffect(() => {
    const param = searchParams.get("view");
    if (param === "split" || param === "zen" || param === "editor") {
      setViewMode((prev) => (prev === param ? prev : param));
    }
  }, [searchParams]);

  useEffect(() => {
    const param = searchParams.get("console");
    if (!param) {
      return;
    }
    const next = param === "open";
    setConsoleOpen((prev) => (prev === next ? prev : next));
  }, [searchParams]);

  useEffect(() => {
    updatePrefs((prev) => ({ ...prev, consoleOpen: isConsoleOpen }));
  }, [isConsoleOpen, updatePrefs]);

  useEffect(() => {
    updatePrefs((prev) => ({ ...prev, viewMode }));
  }, [updatePrefs, viewMode]);

  useEffect(() => {
    updatePrefs((prev) => ({ ...prev, consoleHeight }));
  }, [consoleHeight, updatePrefs]);

  const handlePathChange = useCallback(
    (path: string | null) => {
      updatePrefs((prev) => ({ ...prev, lastPath: path ?? null }));
      updateSearch((params) => {
        if (path) {
          params.set("path", path);
        } else {
          params.delete("path");
        }
      });
    },
    [updatePrefs, updateSearch],
  );

  const editor = useEditorState({ adapter, onPathChange: handlePathChange, onRefreshRequested: refreshTree });

  const pathParam = searchParams.get("path");
  useEffect(() => {
    const target = pathParam ?? prefs.lastPath;
    if (target) {
      void editor.openPath(target);
    }
  }, [editor, pathParam, prefs.lastPath]);

  const fileItems = useMemo(() => flattenFiles(tree), [tree]);

  const toggleConsole = useCallback(() => {
    setConsoleOpen((prev) => {
      const next = !prev;
      updateSearch((params) => {
        if (next) {
          params.set("console", "open");
        } else {
          params.set("console", "closed");
        }
      });
      return next;
    });
  }, [updateSearch]);

  const toggleExplorer = useCallback(() => {
    updatePrefs((prev) => ({ ...prev, explorerCollapsed: !prev.explorerCollapsed }));
  }, [updatePrefs]);

  const toggleSplit = useCallback(() => {
    setViewMode((prev) => {
      const next = prev === "split" ? "editor" : "split";
      updateSearch((params) => {
        if (next === "editor") {
          params.delete("view");
        } else {
          params.set("view", next);
        }
      });
      return next;
    });
  }, [updateSearch]);

  const toggleZen = useCallback(() => {
    setViewMode((prev) => {
      const next = prev === "zen" ? "editor" : "zen";
      updateSearch((params) => {
        if (next === "editor") {
          params.delete("view");
        } else {
          params.set("view", next);
        }
      });
      return next;
    });
  }, [updateSearch]);

  const handleOpenPath = useCallback(
    (path: string) => {
      updateSearch((params) => {
        params.set("path", path);
      });
      void editor.openPath(path);
    },
    [editor, updateSearch],
  );

  const handleSelectProblem = useCallback(
    (problem: Problem) => {
      if (!problem.path) {
        return;
      }
      handleOpenPath(problem.path);
    },
    [handleOpenPath],
  );

  const handleRename = useCallback(
    async (path: string) => {
      const next = window.prompt("Rename file", path);
      if (!next || next === path) {
        return;
      }
      try {
        await editor.renamePath(path, next);
        updateSearch((params) => {
          if (editor.activePath === path) {
            params.set("path", next);
          }
        });
        void refreshTree();
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Unable to rename file.");
      }
    },
    [editor, refreshTree, updateSearch],
  );

  const handleDelete = useCallback(
    async (path: string) => {
      if (!window.confirm(`Delete ${path}?`)) {
        return;
      }
      try {
        await editor.deletePath(path);
        updateSearch((params) => {
          if (params.get("path") === path) {
            params.delete("path");
          }
        });
        void refreshTree();
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Unable to delete file.");
      }
    },
    [editor, refreshTree, updateSearch],
  );

  const handleDownload = useCallback(
    async (path: string) => {
      try {
        const buffer = await adapter.readFile(path);
        const blob = new Blob([buffer.content], { type: "text/plain" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = buffer.path.split("/").pop() ?? "file";
        document.body.append(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
      } catch (error) {
        window.alert(error instanceof Error ? error.message : "Unable to download file.");
      }
    },
    [adapter],
  );

  const handleExplorerDragStart = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      event.preventDefault();
      setExplorerResizing(true);
    },
    [],
  );

  useEffect(() => {
    if (!isExplorerResizing) {
      return;
    }
    const handleMove = (event: MouseEvent) => {
      const rect = layoutRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      const nextWidth = Math.max(220, Math.min(event.clientX - rect.left, 480));
      setExplorerWidth(nextWidth);
      updatePrefs((prev) => ({ ...prev, explorerWidth: nextWidth }));
    };
    const handleUp = () => {
      setExplorerResizing(false);
    };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [isExplorerResizing, updatePrefs]);

  useKeyboardShortcuts({
    onToggleExplorer: toggleExplorer,
    onToggleConsole: toggleConsole,
    onSave: editor.saveActive,
    onQuickOpen: () => setPaletteOpen(true),
    onSplit: toggleSplit,
    onZen: toggleZen,
  });

  const explorerCollapsed = viewMode !== "zen" ? prefs.explorerCollapsed : true;
  const showExplorer = viewMode !== "zen";

  const explorerPanel = showExplorer ? (
    <div
      className="min-h-0 flex-shrink-0"
      style={{ width: explorerCollapsed ? 56 : explorerWidth }}
    >
      {explorerCollapsed ? (
        <div className="flex h-full items-start justify-center p-3">
          <button
            type="button"
            onClick={toggleExplorer}
            className="rounded-xl border border-slate-800/40 bg-slate-900/80 px-3 py-2 text-xs text-slate-200"
          >
            Files
          </button>
        </div>
      ) : (
        <div className="flex h-full flex-col rounded-2xl border border-slate-800/40 bg-slate-950/80">
          <div className="flex items-center justify-between border-b border-slate-800/60 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">Files</p>
            <Button size="xs" variant="ghost" onClick={refreshTree} isLoading={treeLoading}>
              Refresh
            </Button>
          </div>
          <div className="min-h-0 flex-1">
            {treeError ? (
              <div className="p-4 text-sm text-red-300">{treeError}</div>
            ) : tree.length === 0 ? (
              <div className="p-4 text-sm text-slate-400">No files found.</div>
            ) : (
              <ExplorerTree
                nodes={tree}
                activePath={editor.activePath}
                onOpenPath={handleOpenPath}
                onRenamePath={handleRename}
                onDeletePath={handleDelete}
                onDownloadPath={handleDownload}
              />
            )}
          </div>
        </div>
      )}
    </div>
  ) : null;

  return (
    <div className="flex h-full flex-col gap-4">
      <TopBar
        currentPath={editor.activePath}
        statusText={editor.statusText}
        onSelectPath={handleOpenPath}
        onRun={() => void editor.run(editor.activePath ?? undefined)}
        onValidate={() => void editor.validate(editor.activePath ?? undefined)}
        onToggleConsole={toggleConsole}
      />
      <div className="flex min-h-0 flex-1 flex-col gap-4">
        <div className="flex min-h-0 flex-1 gap-4" ref={layoutRef}>
          {explorerPanel}
          {showExplorer && !explorerCollapsed ? (
            <div
              className="w-2 cursor-col-resize"
              onMouseDown={handleExplorerDragStart}
              aria-label="Resize explorer"
              role="separator"
            />
          ) : null}
          <div className="flex min-h-0 flex-1">
            <EditorSurface
              tabs={editor.tabs}
              activeTab={editor.activeTab}
              onSelectTab={(path) => editor.setActivePath(path)}
              onCloseTab={(path) => editor.closePath(path)}
              onUpdateContent={editor.updateContent}
              onSave={() => void editor.saveActive()}
              onRun={() => void editor.run(editor.activePath ?? undefined)}
              onValidate={() => void editor.validate(editor.activePath ?? undefined)}
              viewMode={viewMode}
              onChangeView={(next) => {
                setViewMode(next);
                updateSearch((params) => {
                  if (next === "editor") {
                    params.delete("view");
                  } else {
                    params.set("view", next);
                  }
                });
              }}
              isSaving={editor.isSaving}
              dirty={editor.dirty}
            />
          </div>
        </div>
        {viewMode === "zen" ? null : (
          <ConsolePanel
            isOpen={isConsoleOpen}
            height={isConsoleOpen ? consoleHeight : 40}
            onResize={(nextHeight) => setConsoleHeight(nextHeight)}
            onToggle={toggleConsole}
            logs={editor.logs}
            problems={editor.problems}
            onClearLogs={editor.clearLogs}
            onSelectProblem={handleSelectProblem}
          />
        )}
      </div>
      <CommandPalette
        isOpen={paletteOpen}
        files={fileItems}
        onSelect={(path) => {
          handleOpenPath(path);
          setPaletteOpen(false);
        }}
        onClose={() => setPaletteOpen(false)}
      />
    </div>
  );
}

function flattenFiles(nodes: readonly FileNode[]): Array<{ path: string; name: string }> {
  const files: Array<{ path: string; name: string }> = [];
  const walk = (items: readonly FileNode[]) => {
    items.forEach((node) => {
      if (node.kind === "file") {
        files.push({ path: node.path, name: node.name });
      }
      if (node.children.length > 0) {
        walk(node.children);
      }
    });
  };
  walk(nodes);
  return files;
}

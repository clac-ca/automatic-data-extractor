import { useCallback, useEffect, useMemo, useReducer, useState } from "react";

import type { ConfigFsAdapter } from "../adapters/ConfigFsAdapter";
import type { Problem, RunLogLine } from "../adapters/types";
import { editorReducer, initialEditorState, isTabDirty, type EditorTabState } from "../state/editorStore";

interface UseEditorStateOptions {
  readonly adapter: ConfigFsAdapter;
  readonly onPathChange?: (path: string | null) => void;
  readonly onRefreshRequested?: () => void;
}

export interface UseEditorStateResult {
  readonly tabs: readonly EditorTabState[];
  readonly activeTab: EditorTabState | null;
  readonly activePath: string | null;
  readonly logs: readonly RunLogLine[];
  readonly problems: readonly Problem[];
  readonly statusText: string;
  readonly dirty: boolean;
  readonly isSaving: boolean;
  readonly openPath: (path: string) => Promise<void>;
  readonly closePath: (path: string) => void;
  readonly setActivePath: (path: string | null) => void;
  readonly updateContent: (path: string, content: string) => void;
  readonly saveActive: () => Promise<void>;
  readonly savePath: (path: string) => Promise<void>;
  readonly renamePath: (fromPath: string, toPath: string) => Promise<void>;
  readonly deletePath: (path: string) => Promise<void>;
  readonly run: (path?: string) => Promise<void>;
  readonly validate: (path?: string) => Promise<void>;
  readonly clearLogs: () => void;
  readonly setProblems: (items: Problem[]) => void;
}

export function useEditorState({ adapter, onPathChange, onRefreshRequested }: UseEditorStateOptions): UseEditorStateResult {
  const [state, dispatch] = useReducer(editorReducer, initialEditorState);
  const [logs, setLogs] = useState<RunLogLine[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [statusText, setStatusText] = useState<string>("Ready");

  const activeTab = useMemo(() => state.tabs.find((tab) => tab.path === state.activePath) ?? null, [state]);
  const dirty = activeTab ? isTabDirty(activeTab) : false;
  const isSaving = activeTab?.isSaving ?? false;

  useEffect(() => {
    onPathChange?.(state.activePath);
  }, [state.activePath, onPathChange]);

  const openPath = useCallback(
    async (path: string) => {
      if (!path) {
        return;
      }
      const existing = state.tabs.find((tab) => tab.path === path && !tab.isLoading);
      if (existing) {
        dispatch({ type: "activate", path });
        setStatusText(`Opened ${existing.name}`);
        return;
      }
      dispatch({ type: "open/start", path });
      try {
        const buffer = await adapter.readFile(path);
        dispatch({ type: "open/success", buffer });
        setStatusText(`Opened ${buffer.path}`);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        dispatch({ type: "open/error", path, error: message });
        setStatusText(message);
      }
    },
    [adapter, state.tabs],
  );

  const closePath = useCallback((path: string) => {
    dispatch({ type: "close", path });
  }, []);

  const setActivePath = useCallback((path: string | null) => {
    dispatch({ type: "activate", path });
  }, []);

  const updateContent = useCallback((path: string, content: string) => {
    dispatch({ type: "update", path, content });
    setStatusText("Unsaved changes");
  }, []);

  const savePath = useCallback(
    async (path: string) => {
      const tab = state.tabs.find((item) => item.path === path);
      if (!tab) {
        return;
      }
      dispatch({ type: "save/start", path });
      try {
        const buffer = await adapter.writeFile(
          { path, content: tab.content, mime: tab.mime, etag: tab.etag },
          tab.etag ? { ifMatch: tab.etag } : undefined,
        );
        const savedAt = new Date().toISOString();
        dispatch({ type: "save/success", buffer, savedAt });
        setStatusText(`Saved · ${new Date(savedAt).toLocaleTimeString()}`);
        onRefreshRequested?.();
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        dispatch({ type: "save/error", path, error: message });
        setStatusText(message);
      }
    },
    [adapter, onRefreshRequested, state.tabs],
  );

  const saveActive = useCallback(async () => {
    if (!state.activePath) {
      return;
    }
    await savePath(state.activePath);
  }, [savePath, state.activePath]);

  const renamePath = useCallback(
    async (fromPath: string, toPath: string) => {
      if (!fromPath || !toPath) {
        return;
      }
      await adapter.renamePath(fromPath, toPath);
      dispatch({ type: "rename", fromPath, toPath });
      setStatusText(`Renamed to ${toPath}`);
      onRefreshRequested?.();
    },
    [adapter, onRefreshRequested],
  );

  const deletePath = useCallback(
    async (path: string) => {
      await adapter.deletePath(path);
      dispatch({ type: "close", path });
      setStatusText(`Deleted ${path}`);
      onRefreshRequested?.();
    },
    [adapter, onRefreshRequested],
  );

  const run = useCallback(
    async (path?: string) => {
      const result = await adapter.run(path ? { path } : undefined);
      setLogs((prev) => [...prev, ...result.logs]);
      setStatusText(`Run completed${path ? ` · ${path}` : ""}`);
    },
    [adapter],
  );

  const validate = useCallback(
    async (path?: string) => {
      const result = await adapter.validate(path ? { path } : undefined);
      setProblems(result.problems);
      setLogs((prev) => [...prev, ...result.logs]);
      if (result.problems.length > 0) {
        setStatusText(`Validation found ${result.problems.length} issue(s)`);
      } else {
        setStatusText("Validation succeeded");
      }
    },
    [adapter],
  );

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  return {
    tabs: state.tabs,
    activeTab,
    activePath: state.activePath,
    logs,
    problems,
    statusText,
    dirty,
    isSaving,
    openPath,
    closePath,
    setActivePath,
    updateContent,
    saveActive,
    savePath,
    renamePath,
    deletePath,
    run,
    validate,
    clearLogs,
    setProblems,
  };
}

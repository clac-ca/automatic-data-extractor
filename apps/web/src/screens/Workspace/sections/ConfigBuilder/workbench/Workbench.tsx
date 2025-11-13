import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { BottomPanel } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { Explorer } from "./components/Explorer";
import { Inspector } from "./components/Inspector";
import { PanelResizeHandle } from "./components/PanelResizeHandle";
import { WorkbenchHeader } from "./components/WorkbenchHeader";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import { useEditorThemePreference } from "./state/useEditorThemePreference";
import type { WorkbenchDataSeed, WorkbenchValidationState } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing } from "./utils/tree";

import { Alert } from "@ui/Alert";
import { PageState } from "@ui/PageState";

import { useConfigFilesQuery } from "@shared/configs/hooks/useConfigFiles";
import { configsKeys } from "@shared/configs/keys";
import { readConfigFileJson } from "@shared/configs/api";
import type { FileReadJson } from "@shared/configs/types";
import { useValidateConfigurationMutation } from "@shared/configs/hooks/useValidateConfiguration";
import { createScopedStorage } from "@shared/storage";
import type { ConfigBuilderConsole } from "@app/nav/urlState";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const INSPECTOR_LIMITS = { min: 260, max: 420 } as const;
const OUTPUT_LIMITS = { min: 140, max: 420 } as const;
const MIN_EDITOR_HEIGHT = 320;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const OUTPUT_HANDLE_THICKNESS = 4; // matches h-1 Tailwind utility on PanelResizeHandle
const CONSOLE_COLLAPSE_MESSAGE =
  "Console closed to keep the editor readable on this screen size. Resize the window or collapse other panes to reopen it.";
const buildTabStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.tabs`;
const buildConsoleStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.console`;
const buildEditorThemeStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.editor-theme`;

interface ConsolePanelPreferences {
  readonly height: number;
  readonly state: ConfigBuilderConsole;
}

interface WorkbenchProps {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly seed?: WorkbenchDataSeed;
}

export function Workbench({ workspaceId, configId, configName, seed }: WorkbenchProps) {
  const queryClient = useQueryClient();
  const {
    fileId,
    pane,
    console: consoleState,
    consoleExplicit,
    setFileId,
    setPane,
    setConsole,
  } = useWorkbenchUrlState();

  const usingSeed = Boolean(seed);
  const filesQuery = useConfigFilesQuery({
    workspaceId,
    configId,
    depth: "infinity",
    sort: "path",
    order: "asc",
    enabled: !usingSeed,
  });

  const tree = useMemo(() => {
    if (seed) {
      return seed.tree;
    }
    if (!filesQuery.data) {
      return null;
    }
    return createWorkbenchTreeFromListing(filesQuery.data);
  }, [seed, filesQuery.data]);

  const consoleLines = useMemo(() => seed?.console ?? [], [seed]);

  const [validationState, setValidationState] = useState<WorkbenchValidationState>(() => ({
    status: seed?.validation?.length ? "success" : "idle",
    messages: seed?.validation ?? [],
    lastRunAt: seed?.validation?.length ? new Date().toISOString() : undefined,
    error: null,
    digest: null,
  }));

  useEffect(() => {
    if (seed?.validation) {
      setValidationState({
        status: "success",
        messages: seed.validation,
        lastRunAt: new Date().toISOString(),
        error: null,
        digest: null,
      });
    }
  }, [seed?.validation]);

  const validateConfiguration = useValidateConfigurationMutation(workspaceId, configId);

  const tabPersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildTabStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const consolePersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildConsoleStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | null>(null);
  if (!initialConsolePrefsRef.current && consolePersistence) {
    initialConsolePrefsRef.current = consolePersistence.get<ConsolePanelPreferences>() ?? null;
  }
  const editorTheme = useEditorThemePreference(buildEditorThemeStorageKey(workspaceId, configId));
  const menuAppearance = editorTheme.resolvedTheme === "vs-dark" ? "dark" : "light";

  const loadFile = useCallback(
    async (path: string) => {
      if (seed) {
        return { content: seed.content[path] ?? "", etag: null };
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configsKeys.file(workspaceId, configId, path),
        queryFn: ({ signal }) => readConfigFileJson(workspaceId, configId, path, signal),
      });
      if (!payload) {
        throw new Error("File could not be loaded.");
      }
      return { content: decodeFileContent(payload), etag: payload.etag ?? null };
    },
    [seed, queryClient, workspaceId, configId],
  );

  const files = useWorkbenchFiles({
    tree,
    initialActiveFileId: fileId,
    loadFile,
    persistence: tabPersistence ?? undefined,
  });

  useUnsavedChangesGuard({ isDirty: files.isDirty });

  const [explorer, setExplorer] = useState({ collapsed: false, width: 280 });
  const [inspector, setInspector] = useState({ collapsed: true, width: 300 });
  const [outputHeight, setOutputHeight] = useState(
    () => initialConsolePrefsRef.current?.height ?? DEFAULT_CONSOLE_HEIGHT,
  );
  const [hasHydratedConsoleState, setHasHydratedConsoleState] = useState(false);
  const [centerPaneEl, setCenterPaneEl] = useState<HTMLDivElement | null>(null);
  const [centerHeight, setCenterHeight] = useState(0);
  const [hasMeasuredCenter, setHasMeasuredCenter] = useState(false);
  const [consoleNotice, setConsoleNotice] = useState<string | null>(null);

  const outputCollapsed = consoleState !== "open";

  useEffect(() => {
    if (!centerPaneEl) {
      setCenterHeight(0);
      setHasMeasuredCenter(false);
      return;
    }
    const measure = () => {
      setCenterHeight(centerPaneEl.getBoundingClientRect().height);
      setHasMeasuredCenter(true);
    };
    measure();

    if (typeof window === "undefined") {
      return;
    }

    if ("ResizeObserver" in window) {
      const observer = new window.ResizeObserver(() => measure());
      observer.observe(centerPaneEl);
      return () => observer.disconnect();
    }

    window.addEventListener("resize", measure);
    return () => {
      window.removeEventListener("resize", measure);
    };
  }, [centerPaneEl]);

  const consoleBounds = useMemo(() => {
    if (!hasMeasuredCenter) {
      return {
        min: MIN_CONSOLE_HEIGHT,
        max: OUTPUT_LIMITS.max,
        canFitMin: true,
        hasMeasurement: false,
      };
    }
    const available = Math.max(0, centerHeight - MIN_EDITOR_HEIGHT - OUTPUT_HANDLE_THICKNESS);
    const max = Math.min(OUTPUT_LIMITS.max, available);
    return {
      min: Math.min(MIN_CONSOLE_HEIGHT, max),
      max,
      canFitMin: available >= MIN_CONSOLE_HEIGHT,
      hasMeasurement: true,
    };
  }, [centerHeight, hasMeasuredCenter]);

  const clampOutputHeight = useCallback(
    (value: number) => {
      const { max } = consoleBounds;
      if (max <= 0) {
        return 0;
      }
      const lower = Math.min(Math.max(MIN_CONSOLE_HEIGHT, 0), max);
      return clamp(value, lower, max);
    },
    [consoleBounds],
  );

  useEffect(() => {
    setOutputHeight((current) => clampOutputHeight(current));
  }, [clampOutputHeight]);

  const openConsole = useCallback(() => {
    if (consoleBounds.hasMeasurement && !consoleBounds.canFitMin) {
      setConsole("closed");
      setConsoleNotice(CONSOLE_COLLAPSE_MESSAGE);
      return false;
    }
    setConsoleNotice(null);
    setConsole("open");
    setOutputHeight((current) => clampOutputHeight(current > 0 ? current : DEFAULT_CONSOLE_HEIGHT));
    return true;
  }, [consoleBounds, clampOutputHeight, setConsole]);

  const closeConsole = useCallback(() => {
    setConsole("closed");
    setConsoleNotice(null);
  }, [setConsole]);

  useEffect(() => {
    if (hasHydratedConsoleState) {
      return;
    }
    const storedState = initialConsolePrefsRef.current?.state;
    if (consoleExplicit || !storedState) {
      setHasHydratedConsoleState(true);
      return;
    }
    if (storedState !== consoleState) {
      setConsole(storedState);
    }
    setHasHydratedConsoleState(true);
  }, [consoleExplicit, consoleState, setConsole, hasHydratedConsoleState]);

  useEffect(() => {
    if (!consolePersistence) {
      return;
    }
    consolePersistence.set<ConsolePanelPreferences>({
      height: outputHeight,
      state: consoleState,
    });
  }, [consolePersistence, outputHeight, consoleState]);

  useEffect(() => {
    if (consoleState !== "open" || !consoleBounds.hasMeasurement) {
      return;
    }
    if (!consoleBounds.canFitMin) {
      setConsole("closed");
      setConsoleNotice(CONSOLE_COLLAPSE_MESSAGE);
      return;
    }
    setOutputHeight((current) => clampOutputHeight(current));
  }, [consoleState, consoleBounds, clampOutputHeight, setConsole]);

  useEffect(() => {
    if (!consoleNotice || typeof window === "undefined") {
      return;
    }
    const timeout = window.setTimeout(() => setConsoleNotice(null), 6000);
    return () => window.clearTimeout(timeout);
  }, [consoleNotice]);

  useEffect(() => {
    const activeId = files.activeTabId;
    if (!activeId) {
      setFileId(undefined);
      return;
    }
    setFileId(activeId);
  }, [files.activeTabId, setFileId]);

  const handleRunValidation = useCallback(() => {
    if (
      usingSeed ||
      validateConfiguration.isPending ||
      !tree ||
      filesQuery.isLoading ||
      filesQuery.isError
    ) {
      return;
    }
    const startedAt = new Date().toISOString();
    openConsole();
    setPane("validation");
    setValidationState((prev) => ({
      ...prev,
      status: "running",
      lastRunAt: startedAt,
      error: null,
    }));
    validateConfiguration.mutate(undefined, {
      onSuccess(result) {
        const issues = result.issues ?? [];
        const messages = issues.map((issue) => ({
          level: "error" as const,
          message: issue.message,
          path: issue.path,
        }));
        setValidationState({
          status: "success",
          messages,
          lastRunAt: startedAt,
          error: null,
          digest: result.content_digest ?? null,
        });
      },
      onError(error) {
        const message = error instanceof Error ? error.message : "Validation failed.";
        setValidationState({
          status: "error",
          messages: [{ level: "error", message }],
          lastRunAt: startedAt,
          error: message,
          digest: null,
        });
      },
    });
  }, [
    usingSeed,
    validateConfiguration,
    tree,
    filesQuery.isLoading,
    filesQuery.isError,
    openConsole,
    setPane,
  ]);

  const isRunningValidation = validationState.status === "running" || validateConfiguration.isPending;
  const canRunValidation =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isRunningValidation;

  const handleToggleOutput = useCallback(() => {
    if (outputCollapsed) {
      void openConsole();
    } else {
      closeConsole();
    }
  }, [outputCollapsed, openConsole, closeConsole]);

  if (!seed && filesQuery.isLoading) {
    return (
      <PageState
        variant="loading"
        title="Loading configuration files"
        description="Fetching workspace configuration files for the workbench."
      />
    );
  }

  if (!seed && filesQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration files"
        description="Try reloading the page or check your connection."
      />
    );
  }

  if (!tree) {
    return (
      <PageState
        variant="empty"
        title="No configuration files found"
        description="Create files in the ADE configuration package to begin editing."
      />
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <WorkbenchHeader
        configName={configName}
        explorerCollapsed={explorer.collapsed}
        inspectorCollapsed={inspector.collapsed}
        outputCollapsed={outputCollapsed}
        onToggleExplorer={() => setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed }))}
        onToggleInspector={() => setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed }))}
        onToggleOutput={handleToggleOutput}
        onValidate={handleRunValidation}
        isValidating={isRunningValidation}
        canValidate={canRunValidation}
        lastValidatedAt={validationState.lastRunAt}
        editorThemePreference={editorTheme.preference}
        onChangeEditorThemePreference={editorTheme.setPreference}
      />

      {consoleNotice ? (
        <Alert tone="info" className="text-sm">
          {consoleNotice}
        </Alert>
      ) : null}

      <div className="flex min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {!explorer.collapsed && files.tree ? (
          <>
            <Explorer
              width={explorer.width}
              tree={files.tree}
              activeFileId={files.activeTab?.id ?? ""}
              openFileIds={files.tabs.map((tab) => tab.id)}
              onSelectFile={(fileId) => {
                files.openFile(fileId);
                setFileId(fileId);
              }}
              theme={menuAppearance}
              onCloseFile={files.closeTab}
              onCloseOtherFiles={files.closeOtherTabs}
              onCloseTabsToRight={files.closeTabsToRight}
              onCloseAllFiles={files.closeAllTabs}
            />
            <PanelResizeHandle
              orientation="vertical"
              onPointerDown={(event) => {
                const startX = event.clientX;
                const startWidth = explorer.width;
                trackPointerDrag(event, (move) => {
                  const delta = move.clientX - startX;
                  const next = clamp(startWidth + delta, EXPLORER_LIMITS.min, EXPLORER_LIMITS.max);
                  setExplorer((prev) => ({ ...prev, width: next }));
                });
              }}
            />
          </>
        ) : null}

        <div ref={setCenterPaneEl} className="flex min-h-0 flex-1 flex-col">
          {outputCollapsed ? (
            <EditorArea
              tabs={files.tabs}
              activeTabId={files.activeTab?.id ?? ""}
              onSelectTab={(tabId) => {
                files.selectTab(tabId);
                setFileId(tabId);
              }}
              onCloseTab={files.closeTab}
              onCloseOtherTabs={files.closeOtherTabs}
              onCloseTabsToRight={files.closeTabsToRight}
              onCloseAllTabs={files.closeAllTabs}
              onContentChange={files.updateContent}
              onMoveTab={files.moveTab}
              editorTheme={editorTheme.resolvedTheme}
              menuAppearance={menuAppearance}
              minHeight={MIN_EDITOR_HEIGHT}
            />
          ) : (
            <div
              className="grid min-h-0 flex-1"
              style={{
                gridTemplateRows: `minmax(${MIN_EDITOR_HEIGHT}px, 1fr) ${OUTPUT_HANDLE_THICKNESS}px ${Math.max(
                  0,
                  outputHeight,
                )}px`,
              }}
            >
              <EditorArea
                tabs={files.tabs}
                activeTabId={files.activeTab?.id ?? ""}
                onSelectTab={(tabId) => {
                  files.selectTab(tabId);
                  setFileId(tabId);
                }}
                onCloseTab={files.closeTab}
                onCloseOtherTabs={files.closeOtherTabs}
                onCloseTabsToRight={files.closeTabsToRight}
                onCloseAllTabs={files.closeAllTabs}
                onContentChange={files.updateContent}
                onMoveTab={files.moveTab}
                editorTheme={editorTheme.resolvedTheme}
                menuAppearance={menuAppearance}
                minHeight={MIN_EDITOR_HEIGHT}
              />
              <PanelResizeHandle
                orientation="horizontal"
                onPointerDown={(event) => {
                  const startY = event.clientY;
                  const startHeight = outputHeight;
                  trackPointerDrag(event, (move) => {
                    const delta = startY - move.clientY;
                    const next = clampOutputHeight(startHeight + delta);
                    setOutputHeight(next);
                  });
                }}
              />
              <BottomPanel
                height={Math.max(0, outputHeight)}
                consoleLines={consoleLines}
                validation={validationState}
                activePane={pane}
                onPaneChange={setPane}
              />
            </div>
          )}
        </div>

        {!inspector.collapsed && files.activeTab ? (
          <>
            <PanelResizeHandle
              orientation="vertical"
              onPointerDown={(event) => {
                const startX = event.clientX;
                const startWidth = inspector.width;
                trackPointerDrag(event, (move) => {
                  const delta = startX - move.clientX;
                  const next = clamp(startWidth + delta, INSPECTOR_LIMITS.min, INSPECTOR_LIMITS.max);
                  setInspector((prev) => ({ ...prev, width: next }));
                });
              }}
            />
            <Inspector width={inspector.width} file={files.activeTab} />
          </>
        ) : null}
      </div>
    </div>
  );
}

function decodeFileContent(payload: FileReadJson): string {
  if (payload.encoding === "base64") {
    if (typeof atob === "function") {
      return atob(payload.content);
    }
    const buffer = (globalThis as { Buffer?: { from: (data: string, encoding: string) => { toString: (encoding: string) => string } } }).Buffer;
    if (buffer) {
      return buffer.from(payload.content, "base64").toString("utf-8");
    }
  }
  return payload.content;
}

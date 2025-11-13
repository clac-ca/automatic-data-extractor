import { useCallback, useEffect, useMemo, useState } from "react";
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
import type { WorkbenchDataSeed, WorkbenchValidationState } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing } from "./utils/tree";

import { PageState } from "@ui/PageState";

import { useConfigFilesQuery } from "@shared/configs/hooks/useConfigFiles";
import { configsKeys } from "@shared/configs/keys";
import { readConfigFileJson } from "@shared/configs/api";
import type { FileReadJson } from "@shared/configs/types";
import { useValidateConfigurationMutation } from "@shared/configs/hooks/useValidateConfiguration";
import { createScopedStorage } from "@shared/storage";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const INSPECTOR_LIMITS = { min: 260, max: 420 } as const;
const OUTPUT_LIMITS = { min: 140, max: 420 } as const;
const buildTabStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.tabs`;

interface WorkbenchProps {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly seed?: WorkbenchDataSeed;
}

export function Workbench({ workspaceId, configId, configName, seed }: WorkbenchProps) {
  const queryClient = useQueryClient();
  const { fileId, pane, console: consoleState, setFileId, setPane, setConsole } = useWorkbenchUrlState();

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
  const [outputHeight, setOutputHeight] = useState(200);

  const outputCollapsed = consoleState !== "open";

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
    setConsole("open");
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
    setConsole,
    setPane,
  ]);

  const isRunningValidation = validationState.status === "running" || validateConfiguration.isPending;
  const canRunValidation =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isRunningValidation;

  const handleToggleOutput = () => {
    setConsole(outputCollapsed ? "open" : "closed");
  };

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
    <div className="flex h-full flex-col gap-4">
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
      />

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

        <div className="flex min-h-0 flex-1 flex-col">
          <EditorArea
            tabs={files.tabs}
            activeTabId={files.activeTab?.id ?? ""}
            onSelectTab={(tabId) => {
              files.selectTab(tabId);
              setFileId(tabId);
            }}
            onCloseTab={files.closeTab}
            onContentChange={files.updateContent}
          />

          {!outputCollapsed ? (
            <>
              <PanelResizeHandle
                orientation="horizontal"
                onPointerDown={(event) => {
                  const startY = event.clientY;
                  const startHeight = outputHeight;
                  trackPointerDrag(event, (move) => {
                    const delta = startY - move.clientY;
                    const next = clamp(startHeight + delta, OUTPUT_LIMITS.min, OUTPUT_LIMITS.max);
                    setOutputHeight(next);
                  });
                }}
              />
              <BottomPanel
                height={outputHeight}
                consoleLines={consoleLines}
                validation={validationState}
                activePane={pane}
                onPaneChange={setPane}
              />
            </>
          ) : null}
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

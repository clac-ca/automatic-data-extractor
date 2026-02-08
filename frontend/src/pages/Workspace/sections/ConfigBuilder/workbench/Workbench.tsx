import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ChangeEvent,
} from "react";
import clsx from "clsx";
import { useQueryClient } from "@tanstack/react-query";

import { useNavigate } from "react-router-dom";

import { BottomPanel } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { PublishConfigurationDialog, type PublishDialogPhase } from "./components/PublishConfigurationDialog";
import { RunExtractionDialog, type RunExtractionSelection } from "./components/RunExtractionDialog";
import { WorkbenchChrome } from "./components/WorkbenchChrome";
import { WorkbenchLayoutSync } from "./components/WorkbenchLayoutSync";
import { WorkbenchSidebar } from "./components/WorkbenchSidebar";
import { WorkbenchSidebarResizeHandle } from "./components/WorkbenchSidebarResizeHandle";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import type { WorkbenchDataSeed } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing, findFileNode, findFirstFile } from "./utils/tree";
import { decodeFileContent, describeError, formatRelative, formatWorkspaceLabel } from "./utils/workbenchHelpers";

import { ContextMenu, type ContextMenuItem } from "@/components/ui/context-menu-simple";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageState } from "@/components/layout";
import { SidebarProvider } from "@/components/ui/sidebar";

import { exportConfiguration, readConfigurationFileJson } from "@/api/configurations/api";
import {
  configurationKeys,
  useConfigurationQuery,
  useConfigurationFilesQuery,
  useConfigurationsQuery,
  useDuplicateConfigurationMutation,
  useReplaceConfigurationMutation,
  useSaveConfigurationFileMutation,
} from "@/pages/Workspace/hooks/configurations";
import { createScopedStorage } from "@/lib/storage";
import { uiStorageKeys } from "@/lib/uiStorageKeys";
import { isDarkMode, useTheme } from "@/providers/theme";
import type { WorkbenchConsoleState } from "./state/workbenchSearchParams";
import { ApiError } from "@/api";
import { useNotifications, type NotificationIntent } from "@/providers/notifications";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { useRunSessionModel, type RunCompletionInfo } from "./state/useRunSessionModel";
import { createLastSelectionStorage, persistLastSelection } from "../storage";
import { normalizeConfigStatus, suggestDuplicateName } from "../utils/configs";

const MIN_EDITOR_HEIGHT = 320;
const MIN_EDITOR_HEIGHT_WITH_CONSOLE = 120;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const COLLAPSED_CONSOLE_BAR_HEIGHT = 40;
const MAX_CONSOLE_LINES = 2_000;
const OUTPUT_HANDLE_THICKNESS = 10; // matches separator handle hit target
const DEFAULT_WORKBENCH_SIDEBAR_WIDTH = 18 * 16;
const MIN_WORKBENCH_SIDEBAR_WIDTH = 220;
const MAX_WORKBENCH_SIDEBAR_WIDTH = 520;
const CONSOLE_COLLAPSE_MESSAGE =
  "Panel closed to keep the editor readable on this screen size. Resize the window or collapse other panes to reopen it.";

function resolveRunFailureMessage(payload?: Record<string, unknown> | null): string {
  const failure = (payload?.failure ?? undefined) as Record<string, unknown> | undefined;
  const failureMessage = typeof failure?.message === "string" ? failure.message.trim() : null;
  const payloadErrorMessage =
    typeof payload?.error_message === "string"
      ? payload.error_message.trim()
      : typeof payload?.errorMessage === "string"
        ? payload.errorMessage.trim()
        : null;
  return failureMessage || payloadErrorMessage || "ADE run failed.";
}

interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: WorkbenchConsoleState;
}

type WorkbenchWindowState = "restored" | "maximized";

interface WorkbenchProps {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly configDisplayName: string;
  readonly seed?: WorkbenchDataSeed;
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onMaximizeWindow: () => void;
  readonly onRestoreWindow: () => void;
  readonly onCloseWorkbench: () => void;
  readonly shouldBypassUnsavedGuard?: () => boolean;
}

export function Workbench({
  workspaceId,
  configId,
  configName,
  configDisplayName,
  seed,
  windowState,
  onMinimizeWindow,
  onMaximizeWindow,
  onRestoreWindow,
  onCloseWorkbench,
  shouldBypassUnsavedGuard,
}: WorkbenchProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const {
    fileId,
    pane,
    console: consoleState,
    consoleExplicit,
    setFileId,
    setPane,
    setConsole,
  } = useWorkbenchUrlState();
  const [runId, setRunId] = useState<string | null>(null);

  const usingSeed = Boolean(seed);
  const configurationQuery = useConfigurationQuery({
    workspaceId,
    configurationId: configId,
    enabled: !usingSeed,
  });
  const filesQuery = useConfigurationFilesQuery({
    workspaceId,
    configId,
    depth: "infinity",
    sort: "path",
    order: "asc",
    enabled: !usingSeed,
  });
  const currentFilesetEtag = filesQuery.data?.fileset_hash ?? null;
  const configStatus = normalizeConfigStatus(configurationQuery.data?.status ?? filesQuery.data?.status);
  const isDraftConfig = configStatus === "draft";
  const isActiveConfig = configStatus === "active";
  const fileCapabilities = filesQuery.data?.capabilities;
  const hasFreshFilesSnapshot = usingSeed || filesQuery.isFetchedAfterMount;
  const hasFreshConfigSnapshot = usingSeed || configurationQuery.isFetchedAfterMount;
  const awaitingFreshFilesSnapshot = !usingSeed && !filesQuery.isError && !filesQuery.isFetchedAfterMount;
  const awaitingFreshConfigSnapshot =
    !usingSeed && !configurationQuery.isError && !configurationQuery.isFetchedAfterMount;
  const [publishSucceededReadOnly, setPublishSucceededReadOnly] = useState(false);
  const canEditConfig =
    usingSeed ||
    (hasFreshConfigSnapshot &&
      hasFreshFilesSnapshot &&
      isDraftConfig &&
      Boolean(fileCapabilities?.editable) &&
      !publishSucceededReadOnly);
  const isReadOnlyConfig = !canEditConfig;
  const lastSelectionStorage = useMemo(() => createLastSelectionStorage(workspaceId), [workspaceId]);
  const configurationsQuery = useConfigurationsQuery({ workspaceId, enabled: !usingSeed });
  const existingConfigNames = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    return new Set(items.map((c) => c.display_name.trim().toLowerCase()));
  }, [configurationsQuery.data?.items]);
  const activeConfiguration = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    for (const config of items) {
      if (normalizeConfigStatus(config.status) === "active") {
        return config;
      }
    }
    return null;
  }, [configurationsQuery.data?.items]);
  const duplicateToEdit = useDuplicateConfigurationMutation(workspaceId);

  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState("");
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  const tree = useMemo(() => {
    if (seed) {
      return seed.tree;
    }
    if (!filesQuery.data) {
      return null;
    }
    return createWorkbenchTreeFromListing(filesQuery.data);
  }, [seed, filesQuery.data]);

  useEffect(() => {
    if (!configId) {
      return;
    }
    if (usingSeed || filesQuery.isSuccess) {
      persistLastSelection(lastSelectionStorage, configId);
    }
  }, [configId, usingSeed, filesQuery.isSuccess, lastSelectionStorage]);

  useEffect(() => {
    setPublishDialogOpen(false);
    setPublishDialogPhase("confirm");
    setPublishDialogError(null);
    setIsSubmittingPublish(false);
    setPublishSucceededReadOnly(false);
  }, [configId]);

  const openDuplicateDialog = useCallback(() => {
    duplicateToEdit.reset();
    setDuplicateError(null);
    setDuplicateName(suggestDuplicateName(configDisplayName, existingConfigNames));
    setDuplicateDialogOpen(true);
  }, [configDisplayName, duplicateToEdit, existingConfigNames]);

  const [pendingCompletion, setPendingCompletion] = useState<RunCompletionInfo | null>(null);
  const handleRunComplete = useCallback((info: RunCompletionInfo) => {
    setPendingCompletion(info);
  }, []);
  const replaceConfig = useReplaceConfigurationMutation(workspaceId, configId);
  const replaceInputRef = useRef<HTMLInputElement | null>(null);
  const [actionsMenu, setActionsMenu] = useState<{ x: number; y: number } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [replaceConfirmOpen, setReplaceConfirmOpen] = useState(false);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [publishDialogPhase, setPublishDialogPhase] = useState<PublishDialogPhase>("confirm");
  const [publishDialogError, setPublishDialogError] = useState<string | null>(null);
  const [isSubmittingPublish, setIsSubmittingPublish] = useState(false);

  const {
    runStatus: derivedRunStatus,
    runConnectionState,
    runMode: derivedRunMode,
    runInProgress,
    validation: validationState,
    console,
    latestRun,
    clearConsole,
    startRun,
  } = useRunSessionModel({
    workspaceId,
    configId,
    runId,
    seed,
    maxConsoleLines: MAX_CONSOLE_LINES,
    onRunIdChange: setRunId,
    onRunComplete: handleRunComplete,
  });
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  const tabPersistence = useMemo(
    () => (seed ? null : createScopedStorage(uiStorageKeys.workbenchTabs(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const consolePersistence = useMemo(
    () => (seed ? null : createScopedStorage(uiStorageKeys.workbenchConsole(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | Record<string, unknown> | null>(null);
  const theme = useTheme();
  const menuAppearance = isDarkMode(theme.resolvedMode) ? "dark" : "light";
  const editorThemeId = theme.resolvedMode === "light" ? "vs-light" : "ade-dark";
  const validationLabel = validationState.lastRunAt ? `Last run ${formatRelative(validationState.lastRunAt)}` : undefined;

  const [consoleFraction, setConsoleFraction] = useState<number | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(DEFAULT_WORKBENCH_SIDEBAR_WIDTH);
  const lastConsoleFractionRef = useRef<number | null>(null);
  const [hasHydratedConsoleState, setHasHydratedConsoleState] = useState(false);
  useEffect(() => {
    if (!consolePersistence) {
      initialConsolePrefsRef.current = null;
    } else {
      initialConsolePrefsRef.current =
        (consolePersistence.get<unknown>() as ConsolePanelPreferences | Record<string, unknown> | null) ?? null;
    }
    lastConsoleFractionRef.current = null;
    setConsoleFraction(null);
    setHasHydratedConsoleState(false);
  }, [consolePersistence]);
  const [layoutSize, setLayoutSize] = useState({ width: 0, height: 0 });
  const [paneAreaEl, setPaneAreaEl] = useState<HTMLDivElement | null>(null);
  const [isResizingConsole, setIsResizingConsole] = useState(false);
  const [pendingOpenFileId, setPendingOpenFileId] = useState<string | null>(null);
  const streamErrorBannerRunRef = useRef<string | null>(null);
  const { notifyBanner, dismissScope, notifyToast } = useNotifications();
  const consoleBannerScope = useMemo(
    () => `workbench-console:${workspaceId}:${configId}`,
    [workspaceId, configId],
  );
  const showConsoleBanner = useCallback(
    (message: string, options?: { intent?: NotificationIntent; duration?: number | null }) => {
      notifyBanner({
        title: message,
        intent: options?.intent ?? "info",
        duration: options?.duration ?? 6000,
        dismissible: true,
        scope: consoleBannerScope,
        persistKey: consoleBannerScope,
      });
    },
    [notifyBanner, consoleBannerScope],
  );
  const clearConsoleBanners = useCallback(() => {
    dismissScope(consoleBannerScope, "banner");
  }, [dismissScope, consoleBannerScope]);
  const streamRunMode = derivedRunMode ?? (runInProgress ? "extraction" : undefined);

  useEffect(() => {
    if (streamRunMode === "publish") {
      return;
    }
    if (runConnectionState !== "failed") {
      return;
    }
    const bannerRunKey = runId ?? "__stream_failure__";
    if (streamErrorBannerRunRef.current === bannerRunKey) {
      return;
    }
    streamErrorBannerRunRef.current = bannerRunKey;
    showConsoleBanner("Run stream disconnected. Live logs may be incomplete.", {
      intent: "danger",
      duration: null,
    });
  }, [runConnectionState, runId, showConsoleBanner, streamRunMode]);

  const pushConsoleError = useCallback(
    (error: unknown) => {
      const message = describeError(error);
      showConsoleBanner(message, { intent: "danger", duration: null });
    },
    [showConsoleBanner],
  );

  const handleExportConfig = useCallback(async () => {
    setIsExporting(true);
    try {
      const result = await exportConfiguration(workspaceId, configId);
      const filename = result.filename ?? `${configId}.zip`;
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      showConsoleBanner(`Exported ${filename}`, { intent: "success", duration: 4000 });
    } catch (error) {
      pushConsoleError(error);
      showConsoleBanner("Export failed. Try again in a moment.", { intent: "danger", duration: 6000 });
    } finally {
      setIsExporting(false);
    }
  }, [workspaceId, configId, showConsoleBanner, pushConsoleError]);

  const closeDuplicateDialog = useCallback(() => {
    setDuplicateDialogOpen(false);
    setDuplicateError(null);
  }, []);

  const refreshConfigAfterPublish = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: configurationKeys.files(workspaceId, configId) }),
      queryClient.invalidateQueries({ queryKey: configurationKeys.detail(workspaceId, configId) }),
      queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) }),
    ]);
    await Promise.all([filesQuery.refetch(), configurationsQuery.refetch()]);
    window.setTimeout(() => {
      void filesQuery.refetch();
      void configurationsQuery.refetch();
    }, 600);
  }, [configId, configurationsQuery, filesQuery, queryClient, workspaceId]);

  const handleConfirmDuplicate = useCallback(() => {
    const trimmed = duplicateName.trim();
    if (!trimmed) {
      setDuplicateError("Enter a name for the new draft configuration.");
      return;
    }
    setDuplicateError(null);
    duplicateToEdit.mutate(
      { sourceConfigurationId: configId, displayName: trimmed },
      {
        onSuccess(record) {
          notifyToast({ title: "Draft created.", intent: "success", duration: 3500 });
          closeDuplicateDialog();
          navigate(`/workspaces/${workspaceId}/config-builder/${encodeURIComponent(record.id)}/editor`);
        },
        onError(error) {
          setDuplicateError(error instanceof Error ? error.message : "Unable to duplicate configuration.");
        },
      },
    );
  }, [closeDuplicateDialog, configId, duplicateName, duplicateToEdit, navigate, notifyToast, workspaceId]);

  useEffect(() => {
    if (!pendingCompletion) {
      return;
    }
    const { runId: completedRunId, status, mode, payload } = pendingCompletion;
    const errorMessage = resolveRunFailureMessage(payload);

    if (mode === "publish") {
      setIsSubmittingPublish(false);
      setPublishDialogOpen(true);
      if (status === "succeeded") {
        setPublishSucceededReadOnly(true);
        setPublishDialogError(null);
        setPublishDialogPhase("succeeded");
        void refreshConfigAfterPublish();
      } else {
        const publishFailureSummary = errorMessage === "ADE run failed."
          ? "Publish failed. This configuration remains a draft and is still editable."
          : `Publish failed: ${errorMessage}`;
        setPublishSucceededReadOnly(false);
        setPublishDialogError(publishFailureSummary);
        setPublishDialogPhase("failed");
      }
    } else {
      const notice = status === "succeeded" ? "ADE run completed successfully." : errorMessage;
      const intent: NotificationIntent = status === "succeeded" ? "success" : "danger";
      showConsoleBanner(notice, { intent });
    }

    setPendingCompletion((current) => (current && current.runId === completedRunId ? null : current));
  }, [
    pendingCompletion,
    refreshConfigAfterPublish,
    setPendingCompletion,
    showConsoleBanner,
  ]);

  const isMaximized = windowState === "maximized";
  const isMacPlatform = typeof navigator !== "undefined" ? /mac/i.test(navigator.platform) : false;
  const handleCloseWorkbench = useCallback(() => {
    onCloseWorkbench();
  }, [onCloseWorkbench]);

  const loadFile = useCallback(
    async (path: string) => {
      if (seed) {
        return { content: seed.content[path] ?? "", etag: null };
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configurationKeys.file(workspaceId, configId, path),
        queryFn: ({ signal }) => readConfigurationFileJson(workspaceId, configId, path, signal),
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
  const handleContentChange = useCallback(
    (tabId: string, value: string) => {
      files.updateContent(tabId, value);
    },
    [files],
  );
  const saveConfigFile = useSaveConfigurationFileMutation(workspaceId, configId);
  const reloadFileFromServer = useCallback(
    async (fileId: string) => {
      if (usingSeed) {
        return null;
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configurationKeys.file(workspaceId, configId, fileId),
        queryFn: ({ signal }) => readConfigurationFileJson(workspaceId, configId, fileId, signal),
      });
      const content = decodeFileContent(payload);
      files.replaceTabContent(fileId, {
        content,
        etag: payload.etag ?? null,
        metadata: {
          size: payload.size ?? null,
          modifiedAt: payload.mtime ?? null,
          contentType:
            payload.content_type ??
            files.tabs.find((tab) => tab.id === fileId)?.metadata?.contentType ??
            null,
          etag: payload.etag ?? null,
        },
      });
      return payload;
    },
    [usingSeed, queryClient, workspaceId, configId, files],
  );

  useUnsavedChangesGuard({
    isDirty: files.isDirty,
    shouldBypassNavigation: shouldBypassUnsavedGuard,
  });

  const handleMinimizeWindow = useCallback(() => {
    onMinimizeWindow();
  }, [onMinimizeWindow]);

  const handleToggleMaximize = useCallback(() => {
    if (isMaximized) {
      onRestoreWindow();
    } else {
      onMaximizeWindow();
    }
  }, [isMaximized, onMaximizeWindow, onRestoreWindow]);

  const outputCollapsed = consoleState !== "open";
  const dirtyTabs = useMemo(
    () => files.tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [files.tabs],
  );
  const isSavingTabs = files.tabs.some((tab) => tab.saving);
  const canSaveFiles = !usingSeed && canEditConfig && dirtyTabs.length > 0;

  const saveTab = useCallback(
    async (tabId: string): Promise<boolean> => {
      if (usingSeed) {
        return false;
      }
      const tab = files.tabs.find((entry) => entry.id === tabId);
      if (!tab || tab.status !== "ready") {
        return false;
      }
      if (tab.content === tab.initialContent || tab.saving) {
        return false;
      }
      const contentToSave = tab.content;
      const etagToUse = tab.etag ?? undefined;
      files.beginSavingTab(tabId);
      try {
        const response = await saveConfigFile.mutateAsync({
          path: tab.id,
          content: contentToSave,
          etag: etagToUse,
          create: !etagToUse,
          parents: true,
        });
        const metadata = {
          size: response.size ?? tab.metadata?.size ?? null,
          modifiedAt: response.mtime ?? tab.metadata?.modifiedAt ?? null,
          contentType: tab.metadata?.contentType ?? null,
          etag: response.etag ?? tab.metadata?.etag ?? null,
        };
        files.completeSavingTab(tabId, {
          etag: response.etag ?? tab.etag ?? null,
          metadata,
          savedContent: contentToSave,
        });
        showConsoleBanner(`Saved ${tab.name}`, { intent: "success", duration: 4000 });
        return true;
      } catch (error) {
        const isConcurrencyError = error instanceof ApiError && error.status === 412;
        const failure = isConcurrencyError
          ? new Error("Save blocked because this file changed on the server. Reloading latest version.")
          : error;
        files.failSavingTab(tabId, failure instanceof Error ? failure.message : String(failure));
        if (isConcurrencyError) {
          try {
            await reloadFileFromServer(tabId);
            showConsoleBanner("File reloaded with the latest version from the server. Review before saving again.", {
              intent: "warning",
              duration: 6000,
            });
          } catch (reloadError) {
            pushConsoleError(reloadError);
          }
        }
        pushConsoleError(failure);
        return false;
      }
    },
    [usingSeed, files, saveConfigFile, showConsoleBanner, reloadFileFromServer, pushConsoleError],
  );

  const saveTabsSequentially = useCallback(
    async (tabIds: readonly string[]) => {
      const saved: string[] = [];
      for (const id of tabIds) {
        const result = await saveTab(id);
        if (result) {
          saved.push(id);
        }
      }
      return saved;
    },
    [saveTab],
  );

  const saveDirtyTabsBeforeRun = useCallback(async () => {
    if (!canSaveFiles || dirtyTabs.length === 0) {
      return true;
    }
    const saved = await saveTabsSequentially(dirtyTabs.map((tab) => tab.id));
    const allSaved = saved.length === dirtyTabs.length;
    if (!allSaved) {
      showConsoleBanner("Save failed. Fix errors before running again.", { intent: "danger", duration: 7000 });
    }
    return allSaved;
  }, [canSaveFiles, dirtyTabs, saveTabsSequentially, showConsoleBanner]);

  const handleSaveTabShortcut = useCallback(
    (tabId: string) => {
      void saveTab(tabId);
    },
    [saveTab],
  );

  const handleSaveActiveTab = useCallback(() => {
    if (!files.activeTab) {
      return;
    }
    void saveTab(files.activeTab.id);
  }, [files.activeTab, saveTab]);

  const handleSaveAllTabs = useCallback(() => {
    if (!canSaveFiles) {
      return;
    }
    const ids = dirtyTabs.map((tab) => tab.id);
    void (async () => {
      const saved = await saveTabsSequentially(ids);
      if (saved.length > 1) {
        showConsoleBanner(`Saved ${saved.length} files`, { intent: "success", duration: 5000 });
      }
    })();
  }, [canSaveFiles, dirtyTabs, saveTabsSequentially, showConsoleBanner]);

  useEffect(() => {
    const node = paneAreaEl;
    if (!node || typeof window === "undefined") {
      return;
    }

    const measure = () => {
      const rect = node.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      setLayoutSize({
        width,
        height,
      });
      window.dispatchEvent(new Event("ade:workbench-layout"));
    };

    measure();

    if (typeof window.ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }

    const observer = new window.ResizeObserver(() => measure());
    observer.observe(node);
    return () => observer.disconnect();
  }, [paneAreaEl]);

  const editorMinHeight = outputCollapsed ? MIN_EDITOR_HEIGHT : MIN_EDITOR_HEIGHT_WITH_CONSOLE;
  const consoleLimits = useMemo(() => {
    const container = Math.max(0, layoutSize.height);
    const availableHeight = Math.max(0, container - editorMinHeight - OUTPUT_HANDLE_THICKNESS);
    const maxPx = availableHeight;
    const minPx = Math.min(MIN_CONSOLE_HEIGHT, maxPx);
    return { container, minPx, maxPx };
  }, [layoutSize.height, editorMinHeight]);

  const clampConsoleHeight = useCallback(
    (height: number, limits = consoleLimits) => clamp(height, limits.minPx, limits.maxPx),
    [consoleLimits],
  );

  const resolveInitialConsoleFraction = useCallback(() => {
    const stored = initialConsolePrefsRef.current;
    if (stored && "version" in stored && stored.version === 2 && typeof stored.fraction === "number") {
      return clamp(stored.fraction, 0, 1);
    }
    if (stored && "height" in stored && typeof stored.height === "number" && consoleLimits.container > 0) {
      return clamp(stored.height / consoleLimits.container, 0, 1);
    }
    return 0.25;
  }, [consoleLimits.container]);

  useEffect(() => {
    if (consoleFraction === null && consoleLimits.container > 0) {
      setConsoleFraction(resolveInitialConsoleFraction());
    }
  }, [consoleFraction, consoleLimits.container, resolveInitialConsoleFraction]);

  const openConsole = useCallback(() => {
    if (consoleLimits.container > 0 && consoleLimits.maxPx < MIN_CONSOLE_HEIGHT) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return false;
    }
    clearConsoleBanners();
    setConsole("open");
    setConsoleFraction((current) => {
      if (current !== null) {
        return clamp(current, 0, 1);
      }
      if (lastConsoleFractionRef.current !== null) {
        return clamp(lastConsoleFractionRef.current, 0, 1);
      }
      return resolveInitialConsoleFraction();
    });
    return true;
  }, [consoleLimits, setConsole, showConsoleBanner, clearConsoleBanners, resolveInitialConsoleFraction]);

  const closeConsole = useCallback(() => {
    lastConsoleFractionRef.current = consoleFraction;
    setConsole("closed");
    clearConsoleBanners();
  }, [consoleFraction, setConsole, clearConsoleBanners]);

  useEffect(() => {
    if (hasHydratedConsoleState) {
      return;
    }
    const storedState = initialConsolePrefsRef.current?.state;
    if (consoleExplicit || !storedState) {
      setHasHydratedConsoleState(true);
      return;
    }
    if (storedState === "open" || storedState === "closed") {
      if (storedState !== consoleState) {
        setConsole(storedState);
      }
    }
    setHasHydratedConsoleState(true);
  }, [consoleExplicit, consoleState, setConsole, hasHydratedConsoleState]);

  useEffect(() => {
    if (!consolePersistence || isResizingConsole || consoleFraction === null) {
      return;
    }
    consolePersistence.set<ConsolePanelPreferences>({
      version: 2,
      fraction: clamp(consoleFraction, 0, 1),
      state: consoleState,
    });
  }, [consolePersistence, consoleFraction, consoleState, isResizingConsole]);

  useEffect(() => {
    if (consoleState !== "open" || !consoleLimits.container) {
      return;
    }
    if (consoleLimits.maxPx < MIN_CONSOLE_HEIGHT) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return;
    }
    setConsoleFraction((current) => {
      if (current === null) {
        return resolveInitialConsoleFraction();
      }
      return clamp(current, 0, 1);
    });
  }, [consoleState, consoleLimits, setConsole, showConsoleBanner, resolveInitialConsoleFraction]);

  const paneHeight = Math.max(0, consoleLimits.container);
  const defaultFraction = 0.25;
  const desiredFraction =
    consoleFraction ??
    (paneHeight > 0 ? clamp(DEFAULT_CONSOLE_HEIGHT / paneHeight, 0, 1) : defaultFraction);
  const desiredHeight = desiredFraction * paneHeight;
  const liveConsoleHeight =
    paneHeight > 0
      ? clampConsoleHeight(desiredHeight)
      : 0;
  const effectiveHandle = OUTPUT_HANDLE_THICKNESS;
  const effectiveConsoleHeight = outputCollapsed ? COLLAPSED_CONSOLE_BAR_HEIGHT : liveConsoleHeight;
  const editorHeight =
    paneHeight > 0
      ? Math.max(editorMinHeight, paneHeight - effectiveHandle - effectiveConsoleHeight)
      : editorMinHeight;

  useEffect(() => {
    const activeId = files.activeTabId;
    if (!activeId) {
      setFileId(undefined);
      return;
    }
    setFileId(activeId);
  }, [files.activeTabId, setFileId]);

  useEffect(() => {
    if (!pendingOpenFileId || !tree) {
      return;
    }
    if (!findFileNode(tree, pendingOpenFileId)) {
      return;
    }
    files.openFile(pendingOpenFileId);
    setFileId(pendingOpenFileId);
    setPendingOpenFileId(null);
  }, [pendingOpenFileId, tree, files, setFileId]);

  const prepareRun = useCallback(() => {
    const opened = openConsole();
    if (!opened) {
      return false;
    }
    setPane("terminal");
    return true;
  }, [openConsole, setPane]);

  const handleRunValidation = useCallback(async () => {
    if (usingSeed || !tree || filesQuery.isLoading || filesQuery.isError) {
      return;
    }
    const ready = await saveDirtyTabsBeforeRun();
    if (!ready) {
      return;
    }
    await startRun(
      { operation: "validate" },
      { mode: "validation" },
      { prepare: prepareRun },
    );
  }, [
    usingSeed,
    tree,
    filesQuery.isLoading,
    filesQuery.isError,
    saveDirtyTabsBeforeRun,
    startRun,
    prepareRun,
  ]);

  const startPublishRun = useCallback(async () => {
    if (
      isSubmittingPublish ||
      usingSeed ||
      !isDraftConfig ||
      isReadOnlyConfig ||
      filesQuery.isLoading ||
      filesQuery.isError
    ) {
      return;
    }
    setPublishDialogOpen(true);
    setPublishDialogPhase("running");
    setPublishDialogError(null);
    setIsSubmittingPublish(true);
    closeConsole();
    const ready = await saveDirtyTabsBeforeRun();
    if (!ready) {
      setPublishDialogPhase("failed");
      setPublishDialogError("Save failed. Fix errors before publishing.");
      setIsSubmittingPublish(false);
      return;
    }
    const started = await startRun({ operation: "publish" }, { mode: "publish" });
    if (!started) {
      setPublishDialogPhase("failed");
      setPublishDialogError("Unable to start publish run. Please try again.");
      setIsSubmittingPublish(false);
    }
  }, [
    closeConsole,
    filesQuery.isError,
    filesQuery.isLoading,
    isDraftConfig,
    isReadOnlyConfig,
    isSubmittingPublish,
    saveDirtyTabsBeforeRun,
    startRun,
    usingSeed,
  ]);

  const handleRunExtraction = useCallback(
    async (selection: RunExtractionSelection) => {
      setRunDialogOpen(false);
      if (usingSeed || !tree || filesQuery.isLoading || filesQuery.isError) {
        return;
      }
      const ready = await saveDirtyTabsBeforeRun();
      if (!ready) {
        return;
      }
      const worksheetList = Array.from(new Set((selection.sheetNames ?? []).filter(Boolean)));
      void startRun(
        {
          operation: "process",
          input_document_id: selection.documentId,
          input_sheet_names: worksheetList.length ? worksheetList : undefined,
          log_level: selection.logLevel,
        },
        {
          mode: "extraction",
          documentId: selection.documentId,
          documentName: selection.documentName,
          sheetNames: worksheetList,
        },
        { prepare: prepareRun },
      );
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      startRun,
      prepareRun,
      saveDirtyTabsBeforeRun,
    ],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      const usesPrimary = isMacPlatform ? event.metaKey : event.ctrlKey;
      if (!usesPrimary || event.altKey) {
        return;
      }
      if (event.key.toLowerCase() !== "s") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
          return;
        }
      }
      if (!canSaveFiles) {
        return;
      }
      event.preventDefault();
      handleSaveActiveTab();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isMacPlatform, canSaveFiles, handleSaveActiveTab]);

  const activeRunMode = streamRunMode;
  const runBusy = runInProgress;

  const isRunningValidation =
    validationState.status === "running" || (runBusy && activeRunMode === "validation");
  const canRunValidation =
    !usingSeed &&
    Boolean(tree) &&
    !filesQuery.isLoading &&
    !filesQuery.isError &&
    !runBusy &&
    validationState.status !== "running";

  const isRunningPublish = runBusy && activeRunMode === "publish";
  const canPublish =
    isDraftConfig &&
    canEditConfig &&
    !usingSeed &&
    !filesQuery.isLoading &&
    !filesQuery.isError &&
    !runBusy &&
    !replaceConfig.isPending &&
    !isSubmittingPublish;
  const isRunningExtraction = runBusy && activeRunMode === "extraction";
  const canRunExtraction =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !runBusy;
  const canReplaceFromArchive =
    isDraftConfig && !usingSeed && !replaceConfig.isPending && Boolean(currentFilesetEtag);

  const handlePublishRequest = useCallback(() => {
    if (!canPublish) {
      return;
    }
    setPublishDialogError(null);
    setPublishDialogPhase("confirm");
    setPublishDialogOpen(true);
    closeConsole();
  }, [canPublish, closeConsole]);

  const handleOpenActionsMenu = useCallback((position: { x: number; y: number }) => {
    setActionsMenu(position);
  }, []);
  const isPublishDialogActive = publishDialogOpen;
  const handlePublishDialogClose = useCallback(() => {
    if (publishDialogPhase === "running") {
      return;
    }
    setPublishDialogOpen(false);
    setPublishDialogPhase("confirm");
    setPublishDialogError(null);
    setIsSubmittingPublish(false);
  }, [publishDialogPhase]);
  const handlePublishDialogDone = useCallback(() => {
    setPublishDialogOpen(false);
    setPublishDialogPhase("confirm");
    setPublishDialogError(null);
    setIsSubmittingPublish(false);
  }, []);
  const handlePublishDialogDuplicate = useCallback(() => {
    setPublishDialogOpen(false);
    setPublishDialogPhase("confirm");
    setPublishDialogError(null);
    setIsSubmittingPublish(false);
    openDuplicateDialog();
  }, [openDuplicateDialog]);

  const handleToggleOutput = useCallback(() => {
    if (isPublishDialogActive) {
      return;
    }
    if (outputCollapsed) {
      void openConsole();
    } else {
      closeConsole();
    }
  }, [closeConsole, isPublishDialogActive, openConsole, outputCollapsed]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handler = (event: KeyboardEvent) => {
      const usesPrimary = isMacPlatform ? event.metaKey : event.ctrlKey;
      if (!usesPrimary || event.altKey) {
        return;
      }
      const key = event.key?.toLowerCase();
      if (key !== "`" && event.code !== "Backquote") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const insideEditor = typeof target.closest === "function" ? target.closest("[data-editor-area]") : null;
        if (!insideEditor) {
          const tag = target.tagName;
          const role = target.getAttribute("role");
          if (tag === "INPUT" || tag === "TEXTAREA" || role === "textbox" || target.isContentEditable) {
            return;
          }
        }
      }
      event.preventDefault();
      handleToggleOutput();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isMacPlatform, handleToggleOutput]);

  const handleClearConsole = useCallback(() => {
    clearConsole();
  }, [clearConsole]);

  const handleReplaceArchiveRequest = useCallback(() => {
    if (!canReplaceFromArchive) {
      showConsoleBanner("Replace is only available for draft configurations.", { intent: "warning", duration: 6000 });
      setActionsMenu(null);
      return;
    }
    setActionsMenu(null);
    setReplaceConfirmOpen(true);
  }, [canReplaceFromArchive, showConsoleBanner]);

  const handleReplaceFileChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      event.target.value = "";
      if (!file) {
        return;
      }
      try {
        await replaceConfig.mutateAsync({ file, ifMatch: currentFilesetEtag });
        tabPersistence?.clear?.();
        files.closeAllTabs();
        setFileId(undefined);
        const refreshed = await filesQuery.refetch();
        const listing = refreshed.data ?? filesQuery.data ?? null;
        const nextTree = listing ? createWorkbenchTreeFromListing(listing) : null;
        const firstFile = nextTree ? findFirstFile(nextTree) : null;
        setPendingOpenFileId(firstFile?.id ?? null);
        showConsoleBanner("Configuration replaced from archive.", { intent: "success", duration: 6000 });
      } catch (error) {
        const message =
          error instanceof ApiError && error.status === 412
            ? "Replace blocked: the configuration changed on the server. Reload and try again."
            : error instanceof ApiError && error.status === 428
              ? "Replace blocked: refresh the file list and try again."
            : error instanceof Error
              ? error.message
              : "Unable to replace configuration.";
        pushConsoleError(message);
        showConsoleBanner(message, { intent: "danger", duration: 6000 });
      }
    },
    [
      replaceConfig,
      currentFilesetEtag,
      tabPersistence,
      files,
      filesQuery,
      setFileId,
      setPendingOpenFileId,
      showConsoleBanner,
      pushConsoleError,
    ],
  );

  const actionsMenuItems = useMemo<ContextMenuItem[]>(() => {
    const items: ContextMenuItem[] = [];

    if (isDraftConfig) {
      items.push({
        id: "publish",
        label: "Publish",
        disabled: !canPublish,
        onSelect: () => {
          setActionsMenu(null);
          handlePublishRequest();
        },
      });
    }

    items.push({
      id: "duplicate",
      label: "Duplicate to edit",
      onSelect: () => {
        setActionsMenu(null);
        openDuplicateDialog();
      },
    });

    items.push(
      {
        id: "export",
        label: isExporting ? "Exporting…" : "Export (.zip)",
        disabled: isExporting,
        dividerAbove: true,
        onSelect: () => {
          setActionsMenu(null);
          void handleExportConfig();
        },
      },
      {
        id: "replace",
        label: "Import from zip",
        disabled: !canReplaceFromArchive,
        onSelect: handleReplaceArchiveRequest,
      },
    );

    return items;
  }, [
    canPublish,
    canReplaceFromArchive,
    handlePublishRequest,
    handleExportConfig,
    handleReplaceArchiveRequest,
    isDraftConfig,
    isExporting,
    openDuplicateDialog,
  ]);

  useEffect(() => {
    if (typeof document === "undefined" || !isMaximized) {
      return;
    }
    const previous = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.documentElement.style.overflow = previous || "";
    };
  }, [isMaximized]);

  const workspaceLabel = formatWorkspaceLabel(workspaceId);
  const saveShortcutLabel = isMacPlatform ? "⌘S" : "Ctrl+S";
  const toggleConsoleShortcutLabel = isMacPlatform ? "⌘`" : "Ctrl+`";

  if (
    !seed &&
    (configurationQuery.isLoading ||
      awaitingFreshConfigSnapshot ||
      filesQuery.isLoading ||
      awaitingFreshFilesSnapshot)
  ) {
    return (
      <PageState
        variant="loading"
        title="Refreshing configuration"
        description="Checking the latest configuration status and edit permissions."
      />
    );
  }

  if (!seed && configurationQuery.isError) {
    return (
      <PageState
        variant="error"
        title="Unable to load configuration"
        description="Try reloading the page or check your connection."
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
  const rootSurfaceClass = isMaximized ? "bg-background text-foreground" : "bg-transparent text-foreground";
  const windowFrameClass = isMaximized
    ? "fixed inset-0 z-[90] flex flex-col bg-background text-foreground"
    : "flex w-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-card text-foreground";
  const workbenchSidebarStyle = {
    "--sidebar-width": `${sidebarWidth}px`,
    "--sidebar-width-icon": "3.5rem",
  } as CSSProperties;
  const collapsedConsoleTheme = {
    bar: "border-border bg-card text-foreground",
    hint: "text-muted-foreground",
    button: "border-border bg-popover text-foreground hover:border-ring/40 hover:bg-muted",
  };

  return (
    <div
      className={clsx("flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden", rootSurfaceClass)}
    >
      {isMaximized ? <div className="fixed inset-0 z-40 bg-overlay-strong" /> : null}
      <div className={windowFrameClass}>
        <SidebarProvider className="relative min-h-0 w-full flex-1" style={workbenchSidebarStyle}>
          <WorkbenchLayoutSync
            outputCollapsed={outputCollapsed}
            consoleFraction={consoleFraction}
            isMaximized={isMaximized}
            pane={pane}
          />
          <div className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
            <WorkbenchSidebar
              tree={tree}
              activeFileId={files.activeTab?.id ?? ""}
              onSelectFile={(fileId) => {
                files.openFile(fileId);
                setFileId(fileId);
              }}
              configDisplayName={configDisplayName}
            />
            <WorkbenchSidebarResizeHandle
              width={sidebarWidth}
              minWidth={MIN_WORKBENCH_SIDEBAR_WIDTH}
              maxWidth={MAX_WORKBENCH_SIDEBAR_WIDTH}
              onResize={setSidebarWidth}
            />
            <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-card text-card-foreground">
            <WorkbenchChrome
              configName={configName}
              workspaceLabel={workspaceLabel}
              validationLabel={validationLabel}
              canSaveFiles={canSaveFiles}
              isSavingFiles={isSavingTabs}
              onSaveFile={handleSaveActiveTab}
              saveShortcutLabel={saveShortcutLabel}
              onOpenActionsMenu={handleOpenActionsMenu}
              canRunValidation={canRunValidation}
              isRunningValidation={isRunningValidation}
              onRunValidation={handleRunValidation}
              canPublish={canPublish}
              isPublishing={isRunningPublish}
              onPublish={handlePublishRequest}
              canRunExtraction={canRunExtraction}
              isRunningExtraction={isRunningExtraction}
              onRunExtraction={() => {
                if (!canRunExtraction) return;
                setRunDialogOpen(true);
              }}
              consoleOpen={!outputCollapsed}
              onToggleConsole={handleToggleOutput}
              consoleToggleDisabled={isPublishDialogActive}
              appearance={menuAppearance}
              windowState={windowState}
              onMinimizeWindow={handleMinimizeWindow}
              onToggleMaximize={handleToggleMaximize}
              onCloseWindow={handleCloseWorkbench}
              actionsBusy={isExporting || replaceConfig.isPending}
            />
            {!usingSeed ? (
              <div
                className="border-b border-border bg-card px-4 py-3 text-foreground"
                role="status"
                aria-live="polite"
              >
                {isReadOnlyConfig ? (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-0.5">
                      <p className="text-sm font-semibold">Read-only configuration</p>
                      <p className="text-xs text-muted-foreground">
                        {isActiveConfig
                          ? "Active configurations can’t be edited. Duplicate this configuration to create a draft you can change."
                          : "Archived configurations can’t be edited. Duplicate this configuration to create a draft you can change."}
                      </p>
                    </div>
                    <Button size="sm" onClick={openDuplicateDialog}>
                      Duplicate to edit
                    </Button>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-0.5">
                      <p className="text-sm font-semibold">Draft configuration</p>
                      <p className="text-xs text-muted-foreground">
                        Publish this draft to use it for extraction runs.
                        {activeConfiguration ? ` The current active configuration “${activeConfiguration.display_name}” will be archived.` : ""}
                      </p>
                      {files.isDirty ? (
                        <p className="text-xs font-medium text-accent-foreground">Unsaved changes will be saved before publish.</p>
                      ) : null}
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={handlePublishRequest}
                      disabled={!canPublish}
                      title={!canPublish ? "Publish is unavailable while another run is in progress." : undefined}
                    >
                      {isRunningPublish ? "Publishing…" : "Publish"}
                    </Button>
                  </div>
                )}
              </div>
            ) : null}
            <div ref={setPaneAreaEl} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
              <div
                className="grid min-h-0 min-w-0 flex-1"
                style={{
                  height: paneHeight > 0 ? `${paneHeight}px` : undefined,
                  gridTemplateRows: `${Math.max(editorMinHeight, editorHeight)}px ${effectiveHandle}px ${Math.max(
                    0,
                    effectiveConsoleHeight,
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
                  onContentChange={handleContentChange}
                  onSaveTab={handleSaveTabShortcut}
                  onSaveAllTabs={handleSaveAllTabs}
                  onMoveTab={files.moveTab}
                  onRetryTabLoad={files.reloadTab}
                  onPinTab={files.pinTab}
                  onUnpinTab={files.unpinTab}
                  onSelectRecentTab={files.selectRecentTab}
                  editorTheme={editorThemeId}
                  menuAppearance={menuAppearance}
                  canSaveFiles={canSaveFiles}
                  readOnly={isReadOnlyConfig}
                  minHeight={editorMinHeight}
                />
                <div
                  role="separator"
                  aria-orientation="horizontal"
                  className="group relative flex h-[10px] cursor-row-resize select-none items-center"
                  style={{ touchAction: "none" }}
                  onPointerDown={(event) => {
                    setIsResizingConsole(true);
                    const startY = event.clientY;
                    const startHeight = liveConsoleHeight;
                    let didOpen = false;
                    trackPointerDrag(event, {
                      cursor: "row-resize",
                      onMove: (move) => {
                        if (outputCollapsed && !didOpen) {
                          void openConsole();
                          didOpen = true;
                        }
                        if (consoleLimits.maxPx <= 0 || paneHeight <= 0) {
                          return;
                        }
                        const delta = startY - move.clientY;
                        const nextHeight = clamp(startHeight + delta, consoleLimits.minPx, consoleLimits.maxPx);
                        setConsoleFraction(clamp(nextHeight / paneHeight, 0, 1));
                      },
                      onEnd: () => {
                        setIsResizingConsole(false);
                      },
                    });
                  }}
                  onDoubleClick={() => {
                    if (outputCollapsed) {
                      void openConsole();
                    } else {
                      closeConsole();
                    }
                  }}
                  title="Drag to resize · Double-click to hide/show console"
                >
                  <Separator orientation="horizontal" className="w-full" />
                  <span className="sr-only">Resize panel</span>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleToggleOutput();
                    }}
                    className="absolute right-1/2 top-1/2 h-5 w-5 -translate-y-1/2 translate-x-[40%] rounded bg-foreground/70 text-[10px] text-background opacity-0 shadow-sm transition-opacity group-hover:opacity-100 focus:opacity-100 focus:outline-none"
                    aria-label={outputCollapsed ? "Show console" : "Hide console"}
                    title={outputCollapsed ? "Show console" : "Hide console"}
                  >
                    {outputCollapsed ? "▴" : "▾"}
                  </button>
                </div>
                {outputCollapsed ? (
                  <div
                    className={clsx(
                      "flex cursor-pointer items-center justify-between border-t px-4 py-2 text-[12px] shadow-inner",
                      collapsedConsoleTheme.bar,
                    )}
                    onDoubleClick={handleToggleOutput}
                    title="Double-click to show console"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">Console hidden</span>
                      <span className={clsx("text-[11px]", collapsedConsoleTheme.hint)}>
                        (double-click gutter or {toggleConsoleShortcutLabel})
                      </span>
                      {isPublishDialogActive ? (
                        <span className={clsx("text-[11px] font-medium", collapsedConsoleTheme.hint)}>
                          Publish dialog active
                        </span>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={handleToggleOutput}
                      disabled={isPublishDialogActive}
                      className={clsx(
                        "rounded px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition",
                        collapsedConsoleTheme.button,
                        isPublishDialogActive && "cursor-not-allowed opacity-50",
                      )}
                      title="Show console"
                    >
                      Show console
                    </button>
                  </div>
                ) : (
                  <BottomPanel
                    height={Math.max(0, liveConsoleHeight)}
                    console={console}
                    validation={validationState}
                    activePane={pane}
                    onPaneChange={setPane}
                    latestRun={latestRun}
                    onClearConsole={handleClearConsole}
                    runStatus={derivedRunStatus}
                    runConnectionState={runConnectionState}
                    onToggleCollapse={handleToggleOutput}
                    appearance={menuAppearance}
                  />
                )}
              </div>
            </div>
            </div>
          </div>
        </SidebarProvider>
      </div>
      {runDialogOpen ? (
        <RunExtractionDialog
          open={runDialogOpen}
          workspaceId={workspaceId}
          onClose={() => {
            setRunDialogOpen(false);
          }}
          onRun={handleRunExtraction}
        />
      ) : null}
      <input
        ref={replaceInputRef}
        type="file"
        accept=".zip"
        onChange={handleReplaceFileChange}
        className="hidden"
      />
      {replaceConfirmOpen ? (
        <div className="fixed inset-0 z-[var(--app-z-modal)] flex items-center justify-center bg-overlay-strong px-4">
          <div
            className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="replace-config-title"
          >
            <div className="space-y-2">
              <h2 id="replace-config-title" className="text-lg font-semibold text-foreground">
                Import from zip
              </h2>
              <p className="text-sm text-muted-foreground">
                Importing will replace this configuration’s current code with the uploaded archive. Unsaved editor changes
                will be discarded.
              </p>
              {!canReplaceFromArchive ? (
                <p className="text-sm font-medium text-destructive">Only draft configurations can be replaced.</p>
              ) : null}
              {files.isDirty ? (
                <p className="text-sm font-medium text-accent-foreground">You have unsaved changes that will be lost.</p>
              ) : null}
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => setReplaceConfirmOpen(false)}
                disabled={replaceConfig.isPending}
              >
                Cancel
              </Button>
              <Button
                onClick={() => {
                  setReplaceConfirmOpen(false);
                  replaceInputRef.current?.click();
                }}
                disabled={!canReplaceFromArchive || replaceConfig.isPending}
                isLoading={replaceConfig.isPending}
              >
                Continue
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <PublishConfigurationDialog
        open={publishDialogOpen}
        phase={publishDialogPhase}
        isDirty={files.isDirty}
        canPublish={canPublish}
        isSubmitting={isSubmittingPublish}
        runId={runId}
        activeConfigurationName={activeConfiguration?.display_name ?? null}
        connectionState={runConnectionState}
        errorMessage={publishDialogError}
        console={console}
        onCancel={handlePublishDialogClose}
        onStartPublish={() => {
          void startPublishRun();
        }}
        onDone={handlePublishDialogDone}
        onRetryPublish={() => {
          void startPublishRun();
        }}
        onDuplicateToEdit={handlePublishDialogDuplicate}
      />

      <ConfirmDialog
        open={duplicateDialogOpen}
        title="Duplicate configuration"
        description={`Create a new draft based on “${configDisplayName}”.`}
        confirmLabel="Create draft"
        cancelLabel="Cancel"
        onCancel={closeDuplicateDialog}
        onConfirm={handleConfirmDuplicate}
        isConfirming={duplicateToEdit.isPending}
        confirmDisabled={duplicateToEdit.isPending || duplicateName.trim().length === 0}
      >
        <FormField label="New configuration name" required>
          <Input
            value={duplicateName}
            onChange={(event) => setDuplicateName(event.target.value)}
            placeholder="Copy of My Config"
            disabled={duplicateToEdit.isPending}
          />
        </FormField>
        {duplicateError ? <p className="text-sm font-medium text-destructive">{duplicateError}</p> : null}
      </ConfirmDialog>

      <ContextMenu
        open={Boolean(actionsMenu)}
        position={actionsMenu}
        onClose={() => setActionsMenu(null)}
        items={actionsMenuItems}
        appearance={menuAppearance}
      />
    </div>
  );
}

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEventHandler,
  type ReactNode,
  type ChangeEvent,
} from "react";
import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";

import { useNavigate } from "react-router-dom";

import { BottomPanel } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { WorkbenchSidebar } from "./components/WorkbenchSidebar";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import type { WorkbenchDataSeed } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing, findFileNode, findFirstFile } from "./utils/tree";

import { ContextMenu, type ContextMenuItem } from "@/components/ui/context-menu-simple";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageState } from "@/components/layout";
import { SidebarProvider, useSidebar } from "@/components/ui/sidebar";
import {
  ActionsIcon,
  CloseIcon,
  ConsoleIcon,
  GridIcon,
  MinimizeIcon,
  RunIcon,
  SaveIcon,
  SidebarIcon,
  SpinnerIcon,
  WindowMaximizeIcon,
  WindowRestoreIcon,
} from "@/components/icons";

import { exportConfiguration, readConfigurationFileJson, validateConfiguration } from "@/api/configurations/api";
import {
  configurationKeys,
  useConfigurationFilesQuery,
  useConfigurationsQuery,
  useDuplicateConfigurationMutation,
  useMakeActiveConfigurationMutation,
  useReplaceConfigurationMutation,
  useSaveConfigurationFileMutation,
} from "@/pages/Workspace/hooks/configurations";
import type { FileReadJson } from "@/types/configurations";
import { createScopedStorage } from "@/lib/storage";
import { uiStorageKeys } from "@/lib/uiStorageKeys";
import { isDarkMode, useTheme } from "@/providers/theme";
import type { WorkbenchConsoleState, WorkbenchPane } from "./state/workbenchSearchParams";
import { ApiError } from "@/api";
import type { components } from "@/types";
import { fetchDocumentSheets, type DocumentSheet } from "@/api/documents";
import { client } from "@/api/client";
import { useNotifications, type NotificationIntent } from "@/providers/notifications";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
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

interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: WorkbenchConsoleState;
}

type WorkbenchWindowState = "restored" | "maximized";

type DocumentRow = components["schemas"]["DocumentListRow"];
type RunLogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR";
const RUN_LOG_LEVEL_OPTIONS: Array<{ value: RunLogLevel; label: string }> = [
  { value: "DEBUG", label: "Debug" },
  { value: "INFO", label: "Info" },
  { value: "WARNING", label: "Warning" },
  { value: "ERROR", label: "Error" },
];

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
  const filesQuery = useConfigurationFilesQuery({
    workspaceId,
    configId,
    depth: "infinity",
    sort: "path",
    order: "asc",
    enabled: !usingSeed,
  });
  const currentFilesetEtag = filesQuery.data?.fileset_hash ?? null;
  const isDraftConfig = filesQuery.data?.status === "draft";
  const fileCapabilities = filesQuery.data?.capabilities;
  const canEditConfig = usingSeed || Boolean(fileCapabilities?.editable);
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
  const makeActiveConfig = useMakeActiveConfigurationMutation(workspaceId);

  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState("");
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  const [makeActiveDialogOpen, setMakeActiveDialogOpen] = useState(false);
  const [makeActiveDialogState, setMakeActiveDialogState] = useState<
    | { stage: "checking" }
    | { stage: "confirm" }
    | { stage: "issues"; issues: readonly { path: string; message: string }[] }
    | { stage: "error"; message: string }
    | null
  >(null);

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

  const openDuplicateDialog = useCallback(() => {
    duplicateToEdit.reset();
    setDuplicateError(null);
    setDuplicateName(suggestDuplicateName(configDisplayName, existingConfigNames));
    setDuplicateDialogOpen(true);
  }, [configDisplayName, duplicateToEdit, existingConfigNames]);

  useEffect(() => {
    if (!makeActiveDialogOpen || !isDraftConfig || usingSeed) {
      return;
    }
    let cancelled = false;
    setMakeActiveDialogState({ stage: "checking" });
    void validateConfiguration(workspaceId, configId)
      .then((result) => {
        if (cancelled) return;
        if (Array.isArray(result.issues) && result.issues.length > 0) {
          setMakeActiveDialogState({ stage: "issues", issues: result.issues });
          return;
        }
        setMakeActiveDialogState({ stage: "confirm" });
      })
      .catch((error) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : "Unable to validate configuration.";
        setMakeActiveDialogState({ stage: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [configId, isDraftConfig, makeActiveDialogOpen, usingSeed, workspaceId]);

  const [pendingCompletion, setPendingCompletion] = useState<RunCompletionInfo | null>(null);
  const handleRunComplete = useCallback((info: RunCompletionInfo) => {
    setPendingCompletion(info);
  }, []);
  const replaceConfig = useReplaceConfigurationMutation(workspaceId, configId);
  const replaceInputRef = useRef<HTMLInputElement | null>(null);
  const [actionsMenu, setActionsMenu] = useState<{ x: number; y: number } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [replaceConfirmOpen, setReplaceConfirmOpen] = useState(false);

  const {
    runStatus: derivedRunStatus,
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

  const openMakeActiveDialog = useCallback(() => {
    makeActiveConfig.reset();
    setMakeActiveDialogState({ stage: "checking" });
    setMakeActiveDialogOpen(true);
  }, [makeActiveConfig]);

  const closeMakeActiveDialog = useCallback(() => {
    setMakeActiveDialogOpen(false);
    setMakeActiveDialogState(null);
  }, []);

  const handleConfirmMakeActive = useCallback(() => {
    makeActiveConfig.mutate(
      { configurationId: configId },
      {
        async onSuccess() {
          notifyToast({
            title: "Configuration is now active and locked.",
            description: "Duplicate it to make further edits.",
            intent: "success",
            duration: 5000,
          });
          closeMakeActiveDialog();
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: configurationKeys.files(workspaceId, configId) }),
            queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) }),
          ]);
        },
        onError(error) {
          const message = error instanceof Error ? error.message : "Unable to make configuration active.";
          setMakeActiveDialogState({ stage: "error", message });
        },
      },
    );
  }, [closeMakeActiveDialog, configId, makeActiveConfig, notifyToast, queryClient, workspaceId]);

  useEffect(() => {
    if (!pendingCompletion) {
      return;
    }
    const { runId: completedRunId, status, payload } = pendingCompletion;
    const failure = (payload?.failure ?? undefined) as Record<string, unknown> | undefined;
    const failureMessage = typeof failure?.message === "string" ? failure.message.trim() : null;
    const payloadErrorMessage =
      typeof payload?.error_message === "string"
        ? payload.error_message.trim()
        : typeof payload?.errorMessage === "string"
          ? payload.errorMessage.trim()
          : null;
    const errorMessage = failureMessage || payloadErrorMessage || "ADE run failed.";
    const isCancelled = status === "cancelled";
    const notice =
      status === "succeeded"
        ? "ADE run completed successfully."
        : isCancelled
          ? "ADE run cancelled."
          : errorMessage;
    const intent: NotificationIntent =
      status === "succeeded" ? "success" : isCancelled ? "info" : "danger";
    showConsoleBanner(notice, { intent });

    setPendingCompletion((current) => (current && current.runId === completedRunId ? null : current));
  }, [pendingCompletion, showConsoleBanner, setPendingCompletion]);

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
    let document: DocumentRow | null = null;
    try {
      const documents = await fetchRecentDocuments(workspaceId);
      document = documents[0] ?? null;
    } catch (error) {
      notifyToast({
        title: "Unable to load documents for validation.",
        description: describeError(error),
        intent: "warning",
        duration: 5000,
      });
      return;
    }
    if (!document) {
      notifyToast({
        title: "Upload a document to run validation.",
        intent: "warning",
        duration: 5000,
      });
      return;
    }
    await startRun(
      { validate_only: true, input_document_id: document.id },
      { mode: "validation", documentId: document.id, documentName: document.name },
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
    workspaceId,
    notifyToast,
  ]);

  const handleRunExtraction = useCallback(
    async (selection: {
      documentId: string;
      documentName: string;
      sheetNames?: readonly string[];
      logLevel: RunLogLevel;
    }) => {
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

  const activeRunMode = derivedRunMode ?? (runInProgress ? "extraction" : undefined);
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

  const isRunningExtraction = runBusy && activeRunMode !== "validation";
  const canRunExtraction =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !runBusy;
  const canReplaceFromArchive =
    isDraftConfig && !usingSeed && !replaceConfig.isPending && Boolean(currentFilesetEtag);
  const canMakeActive = isDraftConfig && !usingSeed && !files.isDirty && !makeActiveConfig.isPending;

  const handleOpenActionsMenu = useCallback((position: { x: number; y: number }) => {
    setActionsMenu(position);
  }, []);

  const handleToggleOutput = useCallback(() => {
    if (outputCollapsed) {
      void openConsole();
    } else {
      closeConsole();
    }
  }, [outputCollapsed, openConsole, closeConsole]);

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
        id: "make-active",
        label: "Make active",
        disabled: !canMakeActive,
        onSelect: () => {
          setActionsMenu(null);
          openMakeActiveDialog();
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
    canMakeActive,
    canReplaceFromArchive,
    handleExportConfig,
    handleReplaceArchiveRequest,
    isDraftConfig,
    isExporting,
    openDuplicateDialog,
    openMakeActiveDialog,
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
  const rootSurfaceClass = isMaximized ? "bg-background text-foreground" : "bg-transparent text-foreground";
  const windowFrameClass = isMaximized
    ? "fixed inset-0 z-[90] flex flex-col bg-background text-foreground"
    : "flex w-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-card text-foreground";
  const workbenchSidebarStyle: CSSProperties = {
    "--sidebar-width": `${sidebarWidth}px`,
    "--sidebar-width-icon": "3.5rem",
  };
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
              canRunExtraction={canRunExtraction}
              isRunningExtraction={isRunningExtraction}
              onRunExtraction={() => {
                if (!canRunExtraction) return;
                setRunDialogOpen(true);
              }}
              consoleOpen={!outputCollapsed}
              onToggleConsole={handleToggleOutput}
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
                        {filesQuery.data?.status === "active"
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
                        Make this draft active to use it for extraction runs.
                        {activeConfiguration ? ` The current active configuration “${activeConfiguration.display_name}” will be archived.` : ""}
                      </p>
                      {!canMakeActive && files.isDirty ? (
                        <p className="text-xs font-medium text-accent-foreground">Save changes before making active.</p>
                      ) : null}
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={openMakeActiveDialog}
                      disabled={!canMakeActive}
                      title={!canMakeActive && files.isDirty ? "Save changes before making active." : undefined}
                    >
                      Make active
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
                    </div>
                    <button
                      type="button"
                      onClick={handleToggleOutput}
                      className={clsx(
                        "rounded px-3 py-1 text-[11px] font-semibold uppercase tracking-wide transition",
                        collapsedConsoleTheme.button,
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

      <ConfirmDialog
        open={makeActiveDialogOpen}
        title={
          makeActiveDialogState?.stage === "checking"
            ? "Checking configuration…"
            : makeActiveDialogState?.stage === "issues"
              ? "Fix validation issues first"
              : "Make configuration active?"
        }
        description={
          makeActiveDialogState?.stage === "checking"
            ? "Running validation before activation."
            : makeActiveDialogState?.stage === "issues"
              ? "This configuration has validation issues and can’t be activated yet."
              : activeConfiguration
                ? `This becomes the workspace’s live configuration for extraction runs. The current active configuration “${activeConfiguration.display_name}” will be archived.`
                : "This becomes the workspace’s live configuration for extraction runs."
        }
        confirmLabel={
          makeActiveDialogState?.stage === "issues"
            ? "Continue editing"
            : makeActiveDialogState?.stage === "error"
              ? "Close"
              : "Make active"
        }
        cancelLabel="Cancel"
        onCancel={closeMakeActiveDialog}
        onConfirm={() => {
          if (makeActiveDialogState?.stage === "issues") {
            closeMakeActiveDialog();
            return;
          }
          if (makeActiveDialogState?.stage === "error") {
            closeMakeActiveDialog();
            return;
          }
          handleConfirmMakeActive();
        }}
        isConfirming={makeActiveConfig.isPending}
        confirmDisabled={makeActiveDialogState?.stage === "checking" || makeActiveConfig.isPending}
      >
        {makeActiveDialogState?.stage === "checking" ? (
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-primary" aria-hidden="true" />
            <span>Validating…</span>
          </div>
        ) : makeActiveDialogState?.stage === "issues" ? (
          <div className="space-y-2">
            <p className="text-sm text-foreground">Issues:</p>
            <ul className="max-h-56 space-y-2 overflow-auto rounded-lg border border-border bg-muted p-3 text-xs text-foreground">
              {makeActiveDialogState.issues.map((issue) => (
                <li key={`${issue.path}:${issue.message}`} className="space-y-1">
                  <p className="font-semibold">{issue.path}</p>
                  <p className="text-muted-foreground">{issue.message}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : makeActiveDialogState?.stage === "error" ? (
          <p className="text-sm font-medium text-destructive">{makeActiveDialogState.message}</p>
        ) : null}
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

function WorkbenchLayoutSync({
  outputCollapsed,
  consoleFraction,
  isMaximized,
  pane,
}: {
  readonly outputCollapsed: boolean;
  readonly consoleFraction: number | null;
  readonly isMaximized: boolean;
  readonly pane: WorkbenchPane;
}) {
  const { state, openMobile } = useSidebar();

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [state, openMobile, outputCollapsed, consoleFraction, isMaximized, pane]);

  return null;
}

interface WorkbenchSidebarResizeHandleProps {
  readonly width: number;
  readonly minWidth: number;
  readonly maxWidth: number;
  readonly onResize: (width: number) => void;
}

function WorkbenchSidebarResizeHandle({
  width,
  minWidth,
  maxWidth,
  onResize,
}: WorkbenchSidebarResizeHandleProps) {
  const { isMobile } = useSidebar();

  if (isMobile) {
    return null;
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
      aria-valuemin={minWidth}
      aria-valuemax={maxWidth}
      aria-valuenow={Math.round(width)}
      className="group relative hidden h-full w-2 cursor-col-resize select-none md:block"
      onPointerDown={(event) => {
        const startX = event.clientX;
        const startWidth = width;
        trackPointerDrag(event, {
          cursor: "col-resize",
          onMove: (moveEvent) => {
            const delta = moveEvent.clientX - startX;
            const nextWidth = clamp(startWidth + delta, minWidth, maxWidth);
            onResize(nextWidth);
          },
        });
      }}
    >
      <div className="absolute inset-y-0 left-1/2 w-px bg-border transition-colors group-hover:bg-ring/40" />
      <span className="sr-only">Resize sidebar</span>
    </div>
  );
}

function WorkbenchChrome({
  configName,
  workspaceLabel,
  validationLabel,
  canSaveFiles,
  isSavingFiles,
  onSaveFile,
  saveShortcutLabel,
  onOpenActionsMenu,
  canRunValidation,
  isRunningValidation,
  onRunValidation,
  canRunExtraction,
  isRunningExtraction,
  onRunExtraction,
  consoleOpen,
  onToggleConsole,
  appearance,
  windowState,
  onMinimizeWindow,
  onToggleMaximize,
  onCloseWindow,
  actionsBusy = false,
}: {
  readonly configName: string;
  readonly workspaceLabel: string;
  readonly validationLabel?: string;
  readonly canSaveFiles: boolean;
  readonly isSavingFiles: boolean;
  readonly onSaveFile: () => void;
  readonly saveShortcutLabel: string;
  readonly onOpenActionsMenu: (position: { x: number; y: number }) => void;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: () => void;
  readonly consoleOpen: boolean;
  readonly onToggleConsole: () => void;
  readonly appearance: "light" | "dark";
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onToggleMaximize: () => void;
  readonly onCloseWindow: () => void;
  readonly actionsBusy?: boolean;
}) {
  const surfaceClass = "border-border bg-card text-foreground";
  const metaTextClass = "text-muted-foreground";
  const saveButtonClass =
    "bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground";
  const runButtonClass =
    "bg-primary text-primary-foreground hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground";
  const isMaximized = windowState === "maximized";
  const { state, openMobile, isMobile, toggleSidebar } = useSidebar();
  const explorerVisible = isMobile ? openMobile : state === "expanded";
  return (
    <div className={clsx("flex items-center justify-between border-b px-4 py-2", surfaceClass)}>
      <div className="flex min-w-0 items-center gap-3">
        <WorkbenchBadgeIcon />
        <div className="min-w-0 leading-tight">
          <div className={clsx("text-[10px] font-semibold uppercase tracking-[0.35em]", metaTextClass)}>
            Config Workbench
          </div>
          <div className="truncate text-sm font-semibold" title={configName}>
            {configName}
          </div>
          <div className={clsx("text-[11px]", metaTextClass)} title={workspaceLabel}>
            Workspace · {workspaceLabel}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {validationLabel ? <span className={clsx("text-xs", metaTextClass)}>{validationLabel}</span> : null}
        <button
          type="button"
          onClick={onSaveFile}
          disabled={!canSaveFiles}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            saveButtonClass,
          )}
          title={`Save (${saveShortcutLabel})`}
        >
          {isSavingFiles ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <SaveIcon className="h-4 w-4" />}
          {isSavingFiles ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onRunValidation}
          disabled={!canRunValidation}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningValidation ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          {isRunningValidation ? "Running…" : "Run validation"}
        </button>
        <button
          type="button"
          onClick={onRunExtraction}
          disabled={!canRunExtraction}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
          title="Run test run"
        >
          {isRunningExtraction ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          {isRunningExtraction ? "Running…" : "Test run"}
        </button>
        <div className="flex items-center gap-1">
          <ChromeIconButton
            ariaLabel={explorerVisible ? "Hide sidebar" : "Show sidebar"}
            onClick={toggleSidebar}
            appearance={appearance}
            active={explorerVisible}
            icon={<SidebarIcon className={clsx("h-4 w-4", !explorerVisible && "opacity-60")} />}
          />
          <ChromeIconButton
            ariaLabel={consoleOpen ? "Hide console" : "Show console"}
            onClick={onToggleConsole}
            appearance={appearance}
            active={consoleOpen}
            icon={<ConsoleIcon className="h-3.5 w-3.5" />}
          />
        </div>
        <ChromeIconButton
          ariaLabel="Configuration actions"
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            onOpenActionsMenu({ x: rect.right + 8, y: rect.bottom });
          }}
          appearance={appearance}
          disabled={actionsBusy}
          icon={<ActionsIcon className="h-4 w-4" />}
        />
        <div
          className={clsx(
            "flex items-center gap-2 border-l pl-3",
            "border-border/70",
          )}
        >
          <ChromeIconButton
            ariaLabel="Minimize workbench"
            onClick={onMinimizeWindow}
            appearance={appearance}
            icon={<MinimizeIcon className="h-3.5 w-3.5" />}
          />
          <ChromeIconButton
            ariaLabel={isMaximized ? "Restore workbench" : "Maximize workbench"}
            onClick={onToggleMaximize}
            appearance={appearance}
            active={isMaximized}
            icon={
              isMaximized ? <WindowRestoreIcon className="h-3.5 w-3.5" /> : <WindowMaximizeIcon className="h-3.5 w-3.5" />
            }
          />
          <ChromeIconButton
            ariaLabel="Close workbench"
            onClick={onCloseWindow}
            appearance={appearance}
            icon={<CloseIcon className="h-3.5 w-3.5" />}
          />
        </div>
      </div>
    </div>
  );
}

interface RunExtractionDialogProps {
  readonly open: boolean;
  readonly workspaceId: string;
  readonly onClose: () => void;
  readonly onRun: (selection: {
    documentId: string;
    documentName: string;
    sheetNames?: readonly string[];
    logLevel: RunLogLevel;
  }) => void;
}

function RunExtractionDialog({
  open,
  workspaceId,
  onClose,
  onRun,
}: RunExtractionDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const documentsQuery = useQuery<DocumentRow[]>({
    queryKey: ["builder-documents", workspaceId],
    queryFn: ({ signal }) => fetchRecentDocuments(workspaceId, signal),
    staleTime: 60_000,
    enabled: open,
  });
  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  );
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  useEffect(() => {
    if (!open) {
      return;
    }
    if (!documents.length) {
      setSelectedDocumentId("");
      return;
    }
    setSelectedDocumentId((current) => {
      if (current && documents.some((doc) => doc.id === current)) {
        return current;
      }
      return documents[0]?.id ?? "";
    });
  }, [documents, open]);

  const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["builder-document-sheets", workspaceId, selectedDocumentId],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, selectedDocumentId, signal),
    enabled: open && Boolean(selectedDocumentId),
    staleTime: 60_000,
  });
  const sheetOptions = useMemo(
    () => sheetQuery.data ?? [],
    [sheetQuery.data],
  );
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [logLevel, setLogLevel] = useState<RunLogLevel>("INFO");
  useEffect(() => {
    if (!open) {
      return;
    }
    if (!sheetOptions.length) {
      setSelectedSheets([]);
      return;
    }
    setSelectedSheets((current) =>
      current.filter((name) => sheetOptions.some((sheet) => sheet.name === name)),
    );
  }, [open, sheetOptions]);

  const normalizedSheetSelection = useMemo(
    () =>
      Array.from(
        new Set(selectedSheets.filter((name) => sheetOptions.some((sheet) => sheet.name === name))),
      ),
    [selectedSheets, sheetOptions],
  );

  const toggleWorksheet = useCallback((name: string) => {
    setSelectedSheets((current) =>
      current.includes(name) ? current.filter((sheet) => sheet !== name) : [...current, name],
    );
  }, []);

  if (!open) {
    return null;
  }

  const runDisabled = !selectedDocument || documentsQuery.isLoading || documentsQuery.isError;
  const sheetsAvailable = sheetOptions.length > 0;

  const content = (
    <div className="fixed inset-0 z-[var(--app-z-modal)] flex items-center justify-center bg-overlay-strong px-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Select a document</h2>
            <p className="text-sm text-muted-foreground">
              Choose a workspace document and optional worksheet before running a test.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </header>

        {documentsQuery.isError ? (
          <Alert tone="danger">Unable to load documents. Try again later.</Alert>
        ) : documentsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading documents…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">Upload a document in the workspace to run the extractor.</p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="builder-run-document-select">
                Document
              </label>
              <Select
                value={selectedDocumentId || undefined}
                onValueChange={(value) => setSelectedDocumentId(value)}
              >
                <SelectTrigger id="builder-run-document-select" className="w-full">
                  <SelectValue placeholder="Select a document" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((document) => (
                    <SelectItem key={document.id} value={document.id}>
                      {document.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedDocument ? (
                <p className="text-xs text-muted-foreground">
                  Uploaded {formatDocumentTimestamp(selectedDocument.createdAt)} ·{" "}
                  {(selectedDocument.byteSize ?? 0).toLocaleString()} bytes
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="builder-run-log-level-select">
                Log level
              </label>
              <Select value={logLevel} onValueChange={(value) => setLogLevel(value as RunLogLevel)}>
                <SelectTrigger id="builder-run-log-level-select" className="w-full">
                  <SelectValue placeholder="Select a log level" />
                </SelectTrigger>
                <SelectContent>
                  {RUN_LOG_LEVEL_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">Controls the engine runtime verbosity for this run.</p>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">Worksheet</p>
              {sheetQuery.isLoading ? (
                <p className="text-sm text-muted-foreground">Loading worksheets…</p>
              ) : sheetQuery.isError ? (
                <Alert tone="warning">
                  <div className="space-y-2">
                    <p className="text-sm text-foreground">
                      Worksheet metadata is temporarily unavailable. The run will process the entire file unless you retry and
                      pick specific sheets.
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => sheetQuery.refetch()}
                        disabled={sheetQuery.isFetching}
                      >
                        Retry loading
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                        Use all worksheets
                      </Button>
                    </div>
                  </div>
                </Alert>
              ) : sheetsAvailable ? (
                <div className="space-y-3 rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">Worksheets</p>
                      <p className="text-xs text-muted-foreground">
                        {normalizedSheetSelection.length === 0
                          ? "All worksheets will be processed by default. Select specific sheets to narrow the run."
                          : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                              normalizedSheetSelection.length === 1 ? "" : "s"
                            } selected.`}
                      </p>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => setSelectedSheets([])}>
                      Use all worksheets
                    </Button>
                  </div>

                  <div className="max-h-48 space-y-2 overflow-auto rounded-md border border-border p-2">
                    {sheetOptions.map((sheet) => {
                      const checked = normalizedSheetSelection.includes(sheet.name);
                      return (
                        <label
                          key={`${sheet.index}-${sheet.name}`}
                          className="flex items-center gap-2 rounded px-2 py-1 text-sm text-foreground hover:bg-muted"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-border text-primary focus:ring-ring"
                            checked={checked}
                            onChange={() => toggleWorksheet(sheet.name)}
                          />
                          <span className="flex-1 truncate">
                            {sheet.name}
                            {sheet.is_active ? " (active)" : ""}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">This file will be ingested directly.</p>
              )}
            </div>
          </div>
        )}

        <footer className="mt-6 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (!selectedDocument) {
                return;
              }
              onRun({
                documentId: selectedDocument.id,
                documentName: selectedDocument.name,
                sheetNames: normalizedSheetSelection.length > 0 ? normalizedSheetSelection : undefined,
                logLevel,
              });
            }}
            disabled={runDisabled}
          >
            Start test run
          </Button>
        </footer>
      </div>
    </div>
  );

  return typeof document === "undefined" ? null : createPortal(content, document.body);
}

async function fetchRecentDocuments(workspaceId: string, signal?: AbortSignal): Promise<DocumentRow[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspaceId}/documents", {
    params: {
      path: { workspaceId },
      query: { sort: '[{"id":"createdAt","desc":true}]', limit: 50 },
    },
    signal,
  });
  return data?.items ?? [];
}

function formatDocumentTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function ChromeIconButton({
  ariaLabel,
  onClick,
  icon,
  appearance: _appearance,
  active = false,
  disabled = false,
}: {
  readonly ariaLabel: string;
  readonly onClick: MouseEventHandler<HTMLButtonElement>;
  readonly icon: ReactNode;
  readonly appearance: "light" | "dark";
  readonly active?: boolean;
  readonly disabled?: boolean;
}) {
  const baseClass =
    "text-muted-foreground hover:text-foreground hover:bg-muted hover:border-ring/40 focus-visible:ring-ring/40";
  const activeClass = "text-foreground border-ring bg-muted";
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "flex h-7 w-7 items-center justify-center rounded-[4px] border border-transparent text-sm transition focus-visible:outline-none focus-visible:ring-2",
        baseClass,
        active && activeClass,
        disabled && "cursor-not-allowed opacity-50",
      )}
      title={ariaLabel}
    >
      {icon}
    </button>
  );
}

function WorkbenchBadgeIcon() {
  return (
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-md">
      <GridIcon className="h-4 w-4" />
    </span>
  );
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Operation cancelled.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function formatRelative(timestamp?: string): string {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

function formatWorkspaceLabel(workspaceId: string): string {
  if (workspaceId.length <= 12) {
    return workspaceId;
  }
  return `${workspaceId.slice(0, 6)}…${workspaceId.slice(-4)}`;
}

function decodeFileContent(payload: FileReadJson): string {
  if (payload.encoding === "base64") {
    // Preserve UTF-8 characters when decoding base64 payloads from the API.
    const buffer = (globalThis as { Buffer?: { from: (data: string, encoding: string) => { toString: (encoding: string) => string } } }).Buffer;
    if (buffer) {
      return buffer.from(payload.content, "base64").toString("utf-8");
    }
    if (typeof atob === "function") {
      try {
        const binary = atob(payload.content);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
          bytes[index] = binary.charCodeAt(index);
        }
        if (typeof TextDecoder !== "undefined") {
          return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
        }
        let fallback = "";
        for (let index = 0; index < bytes.length; index += 1) {
          fallback += String.fromCharCode(bytes[index]);
        }
        return fallback;
      } catch {
        // Swallow decode errors and fall through to the raw content.
      }
    }
  }
  return payload.content;
}

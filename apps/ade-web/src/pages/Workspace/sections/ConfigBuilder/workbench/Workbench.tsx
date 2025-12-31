import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent as ReactDragEvent,
  type MouseEvent as ReactMouseEvent,
  type MouseEventHandler,
  type ReactNode,
  type ChangeEvent,
} from "react";
import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";

import { useNavigate } from "@app/nav/history";

import { ActivityBar, type ActivityBarView } from "./components/ActivityBar";
import { BottomPanel } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { Explorer } from "./components/Explorer";
import { PanelResizeHandle } from "./components/PanelResizeHandle";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import type {
  WorkbenchDataSeed,
  WorkbenchUploadFile,
} from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing, findFileNode, findFirstFile } from "./utils/tree";
import { hasFileDrag } from "./utils/fileDrop";
import { isAssetsWorkbenchPath, isSafeWorkbenchPath, joinWorkbenchPath, normalizeWorkbenchPath } from "./utils/paths";

import { ContextMenu, type ContextMenuItem } from "@components/ContextMenu";
import { ConfirmDialog } from "@components/ConfirmDialog";
import { SplitButton } from "@components/SplitButton";
import { PageState } from "@components/PageState";
import {
  ActionsIcon,
  CheckIcon,
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
} from "@components/Icons";

import { exportConfiguration, readConfigurationFileJson, validateConfiguration } from "@api/configurations/api";
import {
  configurationKeys,
  useConfigurationFilesQuery,
  useConfigurationsQuery,
  useCreateConfigurationDirectoryMutation,
  useDeleteConfigurationDirectoryMutation,
  useDeleteConfigurationFileMutation,
  useDuplicateConfigurationMutation,
  useMakeActiveConfigurationMutation,
  useReplaceConfigurationMutation,
  useSaveConfigurationFileMutation,
} from "@hooks/configurations";
import type { FileReadJson } from "@schema/configurations";
import { createScopedStorage } from "@utils/storage";
import { isDarkMode, useTheme } from "@components/theme";
import type { WorkbenchConsoleState } from "./state/workbenchSearchParams";
import { ApiError } from "@api";
import type { components } from "@schema";
import { fetchDocumentSheets, type DocumentSheet } from "@api/documents";
import { client } from "@api/client";
import { useNotifications, type NotificationIntent } from "@components/notifications";
import { Select } from "@components/Select";
import { Button } from "@components/Button";
import { Alert } from "@components/Alert";
import { FormField } from "@components/FormField";
import { Input } from "@components/Input";
import { useRunSessionModel, type RunCompletionInfo } from "./state/useRunSessionModel";
import { createLastSelectionStorage, persistLastSelection } from "../storage";
import { normalizeConfigStatus, suggestDuplicateName } from "../utils/configs";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const MIN_EDITOR_HEIGHT = 320;
const MIN_EDITOR_HEIGHT_WITH_CONSOLE = 120;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const COLLAPSED_CONSOLE_BAR_HEIGHT = 40;
const MAX_CONSOLE_LINES = 2_000;
const OUTPUT_HANDLE_THICKNESS = 10; // matches thicker PanelResizeHandle hit target
const ACTIVITY_BAR_WIDTH = 56; // w-14
const CONSOLE_COLLAPSE_MESSAGE =
  "Panel closed to keep the editor readable on this screen size. Resize the window or collapse other panes to reopen it.";
const buildTabStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.configuration.${configId}.tabs`;
const buildConsoleStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.configuration.${configId}.console`;
const buildExplorerExpandedStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.configuration.${configId}.explorer.expanded`;
const buildLayoutStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.configuration.${configId}.layout`;


const ACTIVITY_LABELS: Record<ActivityBarView, string> = {
  explorer: "",
  search: "Search coming soon",
  scm: "Source Control coming soon",
  extensions: "Extensions coming soon",
};

interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: WorkbenchConsoleState;
}

type SideBounds = {
  readonly minPx: number;
  readonly maxPx: number;
  readonly minFrac: number;
  readonly maxFrac: number;
};

type WorkbenchWindowState = "restored" | "maximized";

type WorkbenchUploadItem = {
  readonly file: File;
  readonly relativePath: string;
  readonly targetPath: string;
  readonly exists: boolean;
  readonly etag: string | null;
};

type WorkbenchUploadPlan = {
  readonly folderPath: string;
  readonly items: readonly WorkbenchUploadItem[];
  readonly conflicts: readonly WorkbenchUploadItem[];
  readonly skipped: readonly { readonly relativePath: string; readonly reason: string }[];
};

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
  const [forceRun, setForceRun] = useState(false);

  const tabPersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildTabStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const consolePersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildConsoleStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const layoutPersistence = useMemo(
    () => createScopedStorage(buildLayoutStorageKey(workspaceId, configId)),
    [workspaceId, configId],
  );
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | Record<string, unknown> | null>(null);
  const theme = useTheme();
  const menuAppearance = isDarkMode(theme.resolvedMode) ? "dark" : "light";
  const editorThemeId = theme.resolvedMode === "light" ? "vs-light" : "ade-dark";
  const validationLabel = validationState.lastRunAt ? `Last run ${formatRelative(validationState.lastRunAt)}` : undefined;

  const [explorer, setExplorer] = useState(() => {
    const stored = layoutPersistence.get<{ version?: number; explorer?: { collapsed: boolean; fraction: number } }>();
    return stored?.explorer
      ? { collapsed: Boolean(stored.explorer.collapsed), fraction: stored.explorer.fraction ?? 280 / 1200 }
      : { collapsed: false, fraction: 280 / 1200 };
  });
  const [consoleFraction, setConsoleFraction] = useState<number | null>(null);
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
  const [activityView, setActivityView] = useState<ActivityBarView>("explorer");
  const [settingsMenu, setSettingsMenu] = useState<{ x: number; y: number } | null>(null);
  const [testMenu, setTestMenu] = useState<{ x: number; y: number } | null>(null);
  const [isResizingConsole, setIsResizingConsole] = useState(false);
  const [isCreatingFile, setIsCreatingFile] = useState(false);
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [uploadPlan, setUploadPlan] = useState<WorkbenchUploadPlan | null>(null);
  const [isUploadingFiles, setIsUploadingFiles] = useState(false);
  const [pendingOpenFileId, setPendingOpenFileId] = useState<string | null>(null);
  const [deletingFilePath, setDeletingFilePath] = useState<string | null>(null);
  const [deletingFolderPath, setDeletingFolderPath] = useState<string | null>(null);
  const { notifyBanner, dismissScope, notifyToast } = useNotifications();
  const consoleBannerScope = useMemo(
    () => `workbench-console:${workspaceId}:${configId}`,
    [workspaceId, configId],
  );
  const uploadToastKey = useMemo(() => `workbench-upload:${workspaceId}:${configId}`, [workspaceId, configId]);
  const deleteConfigFile = useDeleteConfigurationFileMutation(workspaceId, configId);
  const createConfigDirectory = useCreateConfigurationDirectoryMutation(workspaceId, configId);
  const deleteConfigDirectory = useDeleteConfigurationDirectoryMutation(workspaceId, configId);
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
    const errorMessage = failureMessage || "ADE run failed.";
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
  const showExplorerPane = !explorer.collapsed;

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

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [explorer.collapsed, explorer.fraction, outputCollapsed, consoleFraction, isMaximized, pane]);

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

  const deriveSideBounds = useCallback(
    (availableWidth: number, limits: { min: number; max: number }): SideBounds => {
      if (availableWidth <= 0) {
        return { minPx: limits.min, maxPx: limits.max, minFrac: 0, maxFrac: 1 };
      }
      const minPx = Math.min(limits.min, availableWidth);
      const maxPx = Math.min(limits.max, availableWidth);
      return {
        minPx,
        maxPx,
        minFrac: minPx / availableWidth,
        maxFrac: maxPx / availableWidth,
      };
    },
    [],
  );

  const contentWidth = Math.max(0, layoutSize.width - ACTIVITY_BAR_WIDTH);
  const explorerBounds = useMemo(() => deriveSideBounds(contentWidth, EXPLORER_LIMITS), [contentWidth, deriveSideBounds]);

  const clampSideFraction = useCallback((fraction: number, bounds: SideBounds) => clamp(fraction, bounds.minFrac, bounds.maxFrac), []);

  useEffect(() => {
    if (contentWidth <= 0) {
      return;
    }
    setExplorer((prev) => {
      if (prev.collapsed) {
        return prev;
      }
      const next = clampSideFraction(prev.fraction, explorerBounds);
      return next === prev.fraction ? prev : { ...prev, fraction: next };
    });
  }, [contentWidth, explorerBounds, clampSideFraction]);

  useEffect(() => {
    layoutPersistence.set({
      version: 2,
      explorer: { collapsed: explorer.collapsed, fraction: explorer.fraction },
    });
  }, [layoutPersistence, explorer]);

  const rawExplorerWidth = explorer.collapsed
    ? 0
    : clamp(explorer.fraction, explorerBounds.minFrac, explorerBounds.maxFrac) * contentWidth;
  const explorerWidth = contentWidth > 0 ? Math.min(rawExplorerWidth, contentWidth) : rawExplorerWidth;
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
      setForceRun(false);
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
        { forceRebuild: forceRun, prepare: prepareRun },
      );
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      startRun,
      forceRun,
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
  const canCreateFiles =
    !usingSeed && !filesQuery.isLoading && !filesQuery.isError && Boolean(fileCapabilities?.can_create);
  const canDeleteFiles = canCreateFiles && !deleteConfigFile.isPending && Boolean(fileCapabilities?.can_delete);
  const canCreateFolders = canCreateFiles && !createConfigDirectory.isPending;
  const canDeleteFolders =
    canCreateFiles && !deleteConfigDirectory.isPending && Boolean(fileCapabilities?.can_delete);
  const canReplaceFromArchive =
    isDraftConfig && !usingSeed && !replaceConfig.isPending && Boolean(currentFilesetEtag);
  const canMakeActive = isDraftConfig && !usingSeed && !files.isDirty && !makeActiveConfig.isPending;

  const handleSelectActivityView = useCallback((view: ActivityBarView) => {
    setActivityView(view);
    if (view === "explorer") {
      setExplorer((prev) => ({ ...prev, collapsed: false }));
    }
  }, []);

  const handleOpenSettingsMenu = useCallback((event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    const rect = event.currentTarget.getBoundingClientRect();
    setSettingsMenu({ x: rect.right + 8, y: rect.top });
  }, []);
  const handleOpenActionsMenu = useCallback((position: { x: number; y: number }) => {
    setActionsMenu(position);
  }, []);

  const closeSettingsMenu = useCallback(() => setSettingsMenu(null), []);

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

  const handleToggleExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const handleHideExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: true }));
  }, []);

  const handleWorkbenchDragOver = useCallback((event: ReactDragEvent<HTMLElement>) => {
    if (!hasFileDrag(event.dataTransfer)) {
      return;
    }
    event.preventDefault();
  }, []);

  const handleWorkbenchDrop = useCallback(
    (event: ReactDragEvent<HTMLElement>) => {
      if (event.defaultPrevented || !hasFileDrag(event.dataTransfer)) {
        return;
      }
      event.preventDefault();
      notifyToast({
        title: "Drop files into the Explorer to upload.",
        description: "Open the Explorer pane, then drop into a folder in the file tree.",
        intent: "info",
        duration: 7000,
        persistKey: uploadToastKey,
        actions: [
          {
            label: "Show Explorer",
            variant: "secondary",
            onSelect: () => setExplorer((prev) => ({ ...prev, collapsed: false })),
          },
        ],
      });
    },
    [notifyToast, uploadToastKey, setExplorer],
  );

  const runUploadPlan = useCallback(
    async (plan: WorkbenchUploadPlan, options: { overwriteExisting: boolean }) => {
      if (usingSeed) {
        notifyToast({
          title: "Uploads aren’t available in demo mode.",
          intent: "warning",
          duration: 6000,
          persistKey: uploadToastKey,
        });
        return;
      }
      if (isReadOnlyConfig) {
        notifyToast({
          title: "This configuration is read-only.",
          description: "Duplicate it to upload files.",
          intent: "warning",
          duration: 7000,
          persistKey: uploadToastKey,
        });
        return;
      }
      if (!canCreateFiles) {
        notifyToast({
          title: "Files are still loading.",
          description: "Wait for the explorer to finish syncing and try again.",
          intent: "info",
          duration: 6000,
          persistKey: uploadToastKey,
        });
        return;
      }
      if (isUploadingFiles) {
        notifyToast({
          title: "Upload already in progress.",
          description: "Wait for the current upload to finish before starting another.",
          intent: "info",
          duration: 6000,
          persistKey: uploadToastKey,
        });
        return;
      }

      const total = plan.items.length;
      if (total === 0) {
        notifyToast({ title: "No files to upload.", intent: "warning", duration: 5000, persistKey: uploadToastKey });
        return;
      }

      setIsUploadingFiles(true);
      notifyToast({
        title: `Uploading ${total} file${total === 1 ? "" : "s"}…`,
        description: plan.folderPath ? `Destination: ${plan.folderPath}` : "Destination: root",
        intent: "info",
        duration: null,
        dismissible: false,
        persistKey: uploadToastKey,
      });

      const uploaded: string[] = [];
      const failures: Array<{ path: string; message: string }> = [];
      try {
        for (const item of plan.items) {
          if (item.exists && !options.overwriteExisting) {
            continue;
          }
          try {
            await saveConfigFile.mutateAsync({
              path: item.targetPath,
              content: item.file,
              parents: true,
              create: !item.exists,
              etag: item.exists ? item.etag ?? undefined : undefined,
              contentType: item.file.type || undefined,
            });
            uploaded.push(item.targetPath);
          } catch (error) {
            const message =
              error instanceof ApiError && error.status === 412
                ? "Upload blocked because the file changed on the server. Refresh and try again."
                : error instanceof ApiError && error.status === 428
                  ? "Upload blocked: refresh the file list and try again."
                  : error instanceof ApiError && error.status === 413
                    ? error.problem?.detail || "File is larger than the allowed limit."
                    : describeError(error);
            failures.push({ path: item.targetPath, message });
          }
        }

        try {
          await filesQuery.refetch();
        } catch {
          // ignore
        }

        for (const path of uploaded) {
          const tab = files.tabs.find((entry) => entry.id === path);
          if (!tab || tab.status !== "ready") {
            continue;
          }
          const isDirty = tab.content !== tab.initialContent;
          if (isDirty) {
            continue;
          }
          try {
            await reloadFileFromServer(path);
          } catch {
            // ignore tab reload failures; next manual reload/save will reconcile
          }
        }
      } finally {
        setIsUploadingFiles(false);
      }

      const skippedCount = plan.skipped.length;
      const uploadedCount = uploaded.length;
      const failedCount = failures.length;
      const intent: NotificationIntent =
        failedCount > 0 ? (uploadedCount > 0 ? "warning" : "danger") : skippedCount > 0 ? "warning" : "success";
      const descriptionParts: string[] = [];
      if (uploadedCount > 0) descriptionParts.push(`${uploadedCount} uploaded`);
      if (skippedCount > 0) descriptionParts.push(`${skippedCount} skipped`);
      if (failedCount > 0) descriptionParts.push(`${failedCount} failed`);

      notifyToast({
        title:
          failedCount > 0
            ? "Upload finished with issues."
            : skippedCount > 0
              ? "Upload finished."
              : "Upload complete.",
        description: descriptionParts.join(" · "),
        intent,
        duration: 8000,
        dismissible: true,
        persistKey: uploadToastKey,
        actions:
          failures.length > 0
            ? [
                {
                  label: "Show errors",
                  variant: "secondary",
                  onSelect: () => {
                    const sample = failures
                      .slice(0, 6)
                      .map((failure) => `${failure.path}: ${failure.message}`)
                      .join(" · ");
                    notifyBanner({
                      title: "Upload errors",
                      description: sample || "Upload errors occurred.",
                      intent: "danger",
                      duration: null,
                      dismissible: true,
                      scope: uploadToastKey,
                      persistKey: `${uploadToastKey}:errors`,
                    });
                  },
                },
              ]
            : undefined,
      });
    },
    [
      canCreateFiles,
      filesQuery,
      isReadOnlyConfig,
      isUploadingFiles,
      notifyBanner,
      notifyToast,
      reloadFileFromServer,
      saveConfigFile,
      uploadToastKey,
      usingSeed,
      files.tabs,
    ],
  );

  const handleUploadFiles = useCallback(
    async (folderPath: string, droppedFiles: readonly WorkbenchUploadFile[]) => {
      if (isUploadingFiles) {
        notifyToast({
          title: "Upload already in progress.",
          description: "Wait for the current upload to finish before dropping more files.",
          intent: "info",
          duration: 6000,
          persistKey: uploadToastKey,
        });
        return;
      }
      if (uploadPlan) {
        notifyToast({
          title: "Resolve the overwrite prompt first.",
          description: "Choose whether to overwrite existing files, then try again.",
          intent: "info",
          duration: 6000,
          persistKey: uploadToastKey,
        });
        return;
      }
      if (!tree) {
        return;
      }
      const normalizedFolder = normalizeWorkbenchPath(folderPath);
      const limits = filesQuery.data?.limits ?? null;

      const items: WorkbenchUploadItem[] = [];
      const skipped: Array<{ relativePath: string; reason: string }> = [];
      const seenPaths = new Set<string>();

      for (const entry of droppedFiles) {
        const relativePath = normalizeWorkbenchPath(entry.relativePath);
        if (!relativePath) {
          skipped.push({ relativePath: entry.relativePath, reason: "Missing file name." });
          continue;
        }
        const targetPath = joinWorkbenchPath(normalizedFolder, relativePath);
        if (!targetPath || !isSafeWorkbenchPath(targetPath)) {
          skipped.push({ relativePath, reason: "Invalid path." });
          continue;
        }
        if (seenPaths.has(targetPath)) {
          skipped.push({ relativePath, reason: "Duplicate path in drop payload." });
          continue;
        }
        seenPaths.add(targetPath);

        const existing = findFileNode(tree, targetPath);
        if (existing && existing.kind === "folder") {
          skipped.push({ relativePath, reason: "A folder with this name already exists." });
          continue;
        }

        const exists = Boolean(existing && existing.kind === "file");
        const etag = exists ? existing?.metadata?.etag ?? null : null;
        if (exists && !etag) {
          skipped.push({ relativePath, reason: "Missing file version. Refresh and try again." });
          continue;
        }

        const maxBytes =
          limits && typeof limits.code_max_bytes === "number" && typeof limits.asset_max_bytes === "number"
            ? isAssetsWorkbenchPath(targetPath)
              ? limits.asset_max_bytes
              : limits.code_max_bytes
            : null;
        if (typeof maxBytes === "number" && entry.file.size > maxBytes) {
          skipped.push({ relativePath, reason: `File exceeds ${maxBytes} bytes.` });
          continue;
        }

        items.push({ file: entry.file, relativePath, targetPath, exists, etag });
      }

      if (items.length === 0) {
        notifyToast({
          title: "No uploadable files.",
          description: skipped.length ? `${skipped.length} item${skipped.length === 1 ? "" : "s"} skipped.` : undefined,
          intent: "warning",
          duration: 7000,
          persistKey: uploadToastKey,
        });
        return;
      }

      const conflicts = items.filter((item) => item.exists);
      const plan: WorkbenchUploadPlan = {
        folderPath: normalizedFolder,
        items,
        conflicts,
        skipped,
      };

      if (conflicts.length > 0) {
        setUploadPlan(plan);
        return;
      }

      await runUploadPlan(plan, { overwriteExisting: false });
    },
    [filesQuery.data?.limits, isUploadingFiles, notifyToast, runUploadPlan, tree, uploadPlan, uploadToastKey],
  );

  const handleCreateFile = useCallback(
    async (folderPath: string, fileName: string) => {
      const trimmed = fileName.trim();
      if (!trimmed) {
        throw new Error("Enter a file name.");
      }
      if (trimmed.includes("..")) {
        throw new Error("File name cannot include '..'.");
      }
      if (isReadOnlyConfig) {
        throw new Error("This configuration is read-only. Duplicate it to edit.");
      }
      if (!canCreateFiles) {
        throw new Error("Files are still loading.");
      }
      const normalizedFolder = folderPath.replace(/\/+$/, "");
      const sanitizedName = trimmed.replace(/^\/+/, "").replace(/\/+/g, "/");
      const candidatePath = normalizedFolder ? `${normalizedFolder}/${sanitizedName}` : sanitizedName;
      const normalizedPath = candidatePath.replace(/\/+/g, "/");
      if (!normalizedPath || normalizedPath.endsWith("/")) {
        throw new Error("Enter a valid file name.");
      }
      if (tree && findFileNode(tree, normalizedPath)) {
        throw new Error("A file or folder with that name already exists.");
      }
      setIsCreatingFile(true);
      try {
        await saveConfigFile.mutateAsync({
          path: normalizedPath,
          content: "",
          parents: true,
          create: true,
        });
        setPendingOpenFileId(normalizedPath);
        await filesQuery.refetch();
        showConsoleBanner(`Created ${normalizedPath}`, { intent: "success", duration: 4000 });
      } catch (error) {
        pushConsoleError(error);
        throw error instanceof Error ? error : new Error("Unable to create file.");
      } finally {
        setIsCreatingFile(false);
      }
    },
    [canCreateFiles, isReadOnlyConfig, tree, saveConfigFile, filesQuery, showConsoleBanner, pushConsoleError],
  );

  const handleCreateFolder = useCallback(
    async (folderPath: string, folderName: string) => {
      const trimmed = folderName.trim();
      if (!trimmed) {
        throw new Error("Enter a folder name.");
      }
      if (trimmed.includes("..")) {
        throw new Error("Folder name cannot include '..'.");
      }
      if (isReadOnlyConfig) {
        throw new Error("This configuration is read-only. Duplicate it to edit.");
      }
      if (!canCreateFolders) {
        throw new Error("Files are still loading.");
      }
      const normalizedParent = folderPath.replace(/\/+$/, "");
      const sanitizedName = trimmed.replace(/^\/+/, "").replace(/\/+/g, "/");
      const candidatePath = normalizedParent ? `${normalizedParent}/${sanitizedName}` : sanitizedName;
      const normalizedPath = candidatePath.replace(/\/+/g, "/").replace(/\/$/, "");
      if (!normalizedPath) {
        throw new Error("Enter a valid folder name.");
      }
      if (tree && findFileNode(tree, normalizedPath)) {
        throw new Error("A file or folder with that name already exists.");
      }
      setIsCreatingFolder(true);
      try {
        await createConfigDirectory.mutateAsync({ path: normalizedPath });
        await filesQuery.refetch();
        showConsoleBanner(`Folder ready: ${normalizedPath}`, { intent: "success", duration: 4000 });
      } catch (error) {
        pushConsoleError(error);
        throw error instanceof Error ? error : new Error("Unable to create folder.");
      } finally {
        setIsCreatingFolder(false);
      }
    },
    [canCreateFolders, isReadOnlyConfig, tree, createConfigDirectory, filesQuery, showConsoleBanner, pushConsoleError],
  );

  const handleDeleteFile = useCallback(
    async (filePath: string) => {
      if (isReadOnlyConfig) {
        throw new Error("This configuration is read-only. Duplicate it to edit.");
      }
      if (!canDeleteFiles) {
        throw new Error("Files are still loading.");
      }
      const target = tree ? findFileNode(tree, filePath) : null;
      if (!tree || !target) {
        throw new Error("File not found in workspace.");
      }
      const confirmDelete =
        typeof window !== "undefined"
          ? window.confirm(`Delete ${filePath}? This cannot be undone.`)
          : true;
      if (!confirmDelete) {
        return;
      }
      setIsCreatingFile(false);
      setDeletingFilePath(filePath);
      try {
        await deleteConfigFile.mutateAsync({ path: filePath, etag: target.metadata?.etag });
        files.closeTab(filePath);
        setPendingOpenFileId((prev) => (prev === filePath ? null : prev));
        await filesQuery.refetch();
        showConsoleBanner(`Deleted ${filePath}`, { intent: "info", duration: 4000 });
      } catch (error) {
        const message =
          error instanceof ApiError && error.status === 428
            ? "Delete blocked: missing latest file version. Reload the explorer and try again."
            : error instanceof Error
              ? error.message
              : "Unable to delete file.";
        pushConsoleError(message);
        throw new Error(message);
      }
      finally {
        setDeletingFilePath((prev) => (prev === filePath ? null : prev));
      }
    },
    [
      canDeleteFiles,
      isReadOnlyConfig,
      tree,
      deleteConfigFile,
      files,
      filesQuery,
      showConsoleBanner,
      pushConsoleError,
      setDeletingFilePath,
    ],
  );

  const handleDeleteFolder = useCallback(
    async (folderPath: string) => {
      if (isReadOnlyConfig) {
        throw new Error("This configuration is read-only. Duplicate it to edit.");
      }
      if (!canDeleteFolders) {
        throw new Error("Files are still loading.");
      }
      const target = tree ? findFileNode(tree, folderPath) : null;
      if (!tree || !target || target.kind !== "folder") {
        throw new Error("Folder not found in workspace.");
      }
      const confirmDelete =
        typeof window !== "undefined"
          ? window.confirm(`Delete folder ${folderPath} and all contents? This cannot be undone.`)
          : true;
      if (!confirmDelete) {
        return;
      }
      setDeletingFolderPath(folderPath);
      try {
        await deleteConfigDirectory.mutateAsync({ path: folderPath, recursive: true });
        setPendingOpenFileId((prev) => (prev === folderPath ? null : prev));
        files.closeTab(folderPath);
        await filesQuery.refetch();
        showConsoleBanner(`Deleted folder ${folderPath}`, { intent: "info", duration: 4000 });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unable to delete folder.";
        pushConsoleError(message);
        throw new Error(message);
      } finally {
        setDeletingFolderPath((prev) => (prev === folderPath ? null : prev));
      }
    },
    [
      canDeleteFolders,
      isReadOnlyConfig,
      tree,
      deleteConfigDirectory,
      files,
      filesQuery,
      showConsoleBanner,
      pushConsoleError,
      setDeletingFolderPath,
    ],
  );

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

  const settingsMenuItems = useMemo<ContextMenuItem[]>(() => {
    const blankIcon = <span className="inline-block h-4 w-4 opacity-0" />;
    return [
      {
        id: "toggle-explorer",
        label: explorer.collapsed ? "Show Explorer" : "Hide Explorer",
        icon: explorer.collapsed ? blankIcon : <CheckIcon className="h-4 w-4 text-brand-400" />,
        onSelect: () => setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-console",
        label: outputCollapsed ? "Show Console" : "Hide Console",
        icon: outputCollapsed ? blankIcon : <CheckIcon className="h-4 w-4 text-brand-400" />,
        onSelect: handleToggleOutput,
      },
    ];
  }, [
    explorer.collapsed,
    outputCollapsed,
    handleToggleOutput,
  ]);
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
  const testMenuItems = useMemo<ContextMenuItem[]>(() => {
    const disabled = !canRunExtraction;
    return [
      {
        id: "test-force",
        label: "Force build and test",
        disabled,
        onSelect: () => {
          setForceRun(true);
          setRunDialogOpen(true);
          setTestMenu(null);
        },
      },
    ];
  }, [canRunExtraction, setForceRun, setRunDialogOpen, setTestMenu]);

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
  const collapsedConsoleTheme = {
    bar: "border-border bg-card text-foreground",
    hint: "text-muted-foreground",
    button: "border-border-strong bg-popover text-foreground hover:border-border-strong hover:bg-muted",
  };

  return (
    <div
      className={clsx("flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden", rootSurfaceClass)}
      onDragOver={handleWorkbenchDragOver}
      onDrop={handleWorkbenchDrop}
    >
      {isMaximized ? <div className="fixed inset-0 z-40 bg-overlay/60" /> : null}
      <div className={windowFrameClass}>
        <WorkbenchChrome
          configName={configName}
          workspaceLabel={workspaceLabel}
          validationLabel={validationLabel}
          canSaveFiles={canSaveFiles}
          isSavingFiles={isSavingTabs}
          onSaveFile={handleSaveActiveTab}
          saveShortcutLabel={saveShortcutLabel}
          onOpenTestMenu={(position) => setTestMenu(position)}
          onOpenActionsMenu={handleOpenActionsMenu}
          canRunValidation={canRunValidation}
          isRunningValidation={isRunningValidation}
          onRunValidation={handleRunValidation}
          canRunExtraction={canRunExtraction}
          isRunningExtraction={isRunningExtraction}
          onRunExtraction={(force) => {
            if (!canRunExtraction) return;
            setForceRun(force);
            setRunDialogOpen(true);
          }}
          explorerVisible={showExplorerPane}
          onToggleExplorer={handleToggleExplorer}
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
                    <p className="text-xs font-medium text-warning-500">Save changes before making active.</p>
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
        <div ref={setPaneAreaEl} className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
          <ActivityBar
            activeView={activityView}
            onSelectView={handleSelectActivityView}
            onOpenSettings={handleOpenSettingsMenu}
            appearance={menuAppearance}
          />
          {showExplorerPane ? (
            <>
              <div className="flex min-h-0" style={{ width: explorerWidth }}>
                {activityView === "explorer" && files.tree ? (
                  <Explorer
                    width={explorerWidth}
                    tree={files.tree}
                    activeFileId={files.activeTab?.id ?? ""}
                    openFileIds={files.tabs.map((tab) => tab.id)}
                    onSelectFile={(fileId) => {
                      files.openFile(fileId);
                      setFileId(fileId);
                    }}
                    theme={menuAppearance}
                    canUploadFiles={canCreateFiles}
                    onUploadFiles={handleUploadFiles}
                    isUploadingFiles={isUploadingFiles}
                    canCreateFile={canCreateFiles}
                    canCreateFolder={canCreateFolders}
                    isCreatingEntry={isCreatingFile || isCreatingFolder}
                    onCreateFile={handleCreateFile}
                    onCreateFolder={handleCreateFolder}
                    canDeleteFile={canDeleteFiles}
                    canDeleteFolder={canDeleteFolders}
                    deletingFilePath={deletingFilePath}
                    deletingFolderPath={deletingFolderPath}
                    onDeleteFile={handleDeleteFile}
                    onDeleteFolder={handleDeleteFolder}
                    expandedStorageKey={buildExplorerExpandedStorageKey(workspaceId, configId)}
                    onHide={handleHideExplorer}
                  />
                ) : (
                  <SidePanelPlaceholder
                    width={explorerWidth}
                    view={activityView}
                    appearance={menuAppearance}
                  />
                )}
              </div>
              <PanelResizeHandle
                orientation="vertical"
                onPointerDown={(event) => {
                  const startX = event.clientX;
                  const startWidth = explorerWidth;
                  trackPointerDrag(event, {
                    cursor: "col-resize",
                    onMove: (move) => {
                      const delta = move.clientX - startX;
                      const nextWidth = clamp(startWidth + delta, explorerBounds.minPx, explorerBounds.maxPx);
                      setExplorer((prev) =>
                        prev.collapsed || contentWidth <= 0
                          ? prev
                          : { ...prev, fraction: clampSideFraction(nextWidth / contentWidth, explorerBounds) },
                      );
                    },
                  });
                }}
              />
            </>
          ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-card text-card-foreground">
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
            <PanelResizeHandle
              orientation="horizontal"
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
              onToggle={handleToggleOutput}
              collapsed={outputCollapsed}
            />
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
      {runDialogOpen ? (
        <RunExtractionDialog
          open={runDialogOpen}
          workspaceId={workspaceId}
          onClose={() => {
            setRunDialogOpen(false);
            setForceRun(false);
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
        <div className="fixed inset-0 z-[95] flex items-center justify-center bg-overlay/60 px-4">
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
                <p className="text-sm font-medium text-danger-600">Only draft configurations can be replaced.</p>
              ) : null}
              {files.isDirty ? (
                <p className="text-sm font-medium text-warning-700">You have unsaved changes that will be lost.</p>
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
        {duplicateError ? <p className="text-sm font-medium text-danger-600">{duplicateError}</p> : null}
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
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-brand-600" aria-hidden="true" />
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
          <p className="text-sm font-medium text-danger-600">{makeActiveDialogState.message}</p>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(uploadPlan)}
        title={uploadPlan && uploadPlan.conflicts.length === 1 ? "Overwrite existing file?" : "Overwrite existing files?"}
        description={
          uploadPlan
            ? `${uploadPlan.conflicts.length} file${uploadPlan.conflicts.length === 1 ? "" : "s"} already exist${
                uploadPlan.folderPath ? ` in “${uploadPlan.folderPath}”.` : " in the configuration root."
              } Overwrite to replace them.`
            : undefined
        }
        confirmLabel={
          uploadPlan
            ? `Overwrite ${uploadPlan.conflicts.length} file${uploadPlan.conflicts.length === 1 ? "" : "s"}`
            : "Overwrite"
        }
        cancelLabel="Cancel"
        onCancel={() => setUploadPlan(null)}
        onConfirm={() => {
          const plan = uploadPlan;
          setUploadPlan(null);
          if (!plan) return;
          void runUploadPlan(plan, { overwriteExisting: true });
        }}
        isConfirming={isUploadingFiles}
        confirmDisabled={!uploadPlan || uploadPlan.conflicts.length === 0 || isUploadingFiles}
        tone="danger"
      >
        {uploadPlan ? (
          <div className="space-y-3">
            <div className="max-h-56 overflow-auto rounded-lg border border-border bg-muted p-3 text-xs text-foreground">
              <p className="font-semibold text-foreground">Will overwrite:</p>
              <ul className="mt-2 space-y-1">
                {uploadPlan.conflicts.slice(0, 20).map((item) => (
                  <li key={item.targetPath} className="break-all">
                    {item.targetPath}
                  </li>
                ))}
              </ul>
              {uploadPlan.conflicts.length > 20 ? (
                <p className="mt-2 text-[11px] text-muted-foreground">And {uploadPlan.conflicts.length - 20} more…</p>
              ) : null}
            </div>
            {uploadPlan.skipped.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                {uploadPlan.skipped.length} item{uploadPlan.skipped.length === 1 ? "" : "s"} will be skipped due to invalid
                paths or size limits.
              </p>
            ) : null}
            {uploadPlan.items.length > uploadPlan.conflicts.length ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground">
                <p className="font-medium">Prefer not to overwrite?</p>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={isUploadingFiles}
                  onClick={() => {
                    const plan = uploadPlan;
                    setUploadPlan(null);
                    void runUploadPlan(plan, { overwriteExisting: false });
                  }}
                >
                  Upload new only ({uploadPlan.items.length - uploadPlan.conflicts.length})
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </ConfirmDialog>

      <ContextMenu
        open={Boolean(actionsMenu)}
        position={actionsMenu}
        onClose={() => setActionsMenu(null)}
        items={actionsMenuItems}
        appearance={menuAppearance}
      />
      <ContextMenu
        open={Boolean(testMenu)}
        position={testMenu}
        onClose={() => setTestMenu(null)}
        items={testMenuItems}
        appearance={menuAppearance}
      />
      <ContextMenu
        open={Boolean(settingsMenu)}
        position={settingsMenu}
        onClose={closeSettingsMenu}
        items={settingsMenuItems}
        appearance={menuAppearance}
      />
    </div>
  );
}

interface SidePanelPlaceholderProps {
  readonly width: number;
  readonly view: ActivityBarView;
  readonly appearance: "light" | "dark";
}

function SidePanelPlaceholder({ width, view, appearance: _appearance }: SidePanelPlaceholderProps) {
  const label = ACTIVITY_LABELS[view] || "Coming soon";
  const surfaceClass = "border-border bg-muted text-muted-foreground";
  return (
    <div
      className={clsx(
        "flex h-full min-h-0 flex-col items-center justify-center border-r px-4 text-center text-[11px] uppercase tracking-wide",
        surfaceClass,
      )}
      style={{ width }}
      aria-live="polite"
    >
      {label}
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
  onOpenTestMenu,
  onOpenActionsMenu,
  canRunValidation,
  isRunningValidation,
  onRunValidation,
  canRunExtraction,
  isRunningExtraction,
  onRunExtraction,
  explorerVisible,
  onToggleExplorer,
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
  readonly onOpenTestMenu: (position: { x: number; y: number }) => void;
  readonly onOpenActionsMenu: (position: { x: number; y: number }) => void;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: (force: boolean) => void;
  readonly explorerVisible: boolean;
  readonly onToggleExplorer: () => void;
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
    "bg-success-600 text-on-success hover:bg-success-500 disabled:bg-muted disabled:text-muted-foreground";
  const runButtonClass =
    "bg-brand-600 text-on-brand hover:bg-brand-500 disabled:bg-muted disabled:text-muted-foreground";
  const isMaximized = windowState === "maximized";
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
        <SplitButton
          label={isRunningExtraction ? "Running…" : "Test run"}
          icon={isRunningExtraction ? <SpinnerIcon className="h-4 w-4 animate-spin" /> : <RunIcon className="h-4 w-4" />}
          disabled={!canRunExtraction}
          isLoading={isRunningExtraction}
          title="Run test run"
          primaryClassName={clsx(
            runButtonClass,
            "rounded-r-none focus-visible:ring-offset-0",
          )}
          menuClassName={clsx(
            runButtonClass,
            "rounded-l-none px-2",
            "border-border-strong",
          )}
          menuAriaLabel="Open test options"
          onPrimaryClick={() => onRunExtraction(false)}
          onOpenMenu={(position) => onOpenTestMenu(position)}
          onContextMenu={(event) => {
            event.preventDefault();
            onOpenTestMenu({ x: event.clientX, y: event.clientY });
          }}
        />
        <div className="flex items-center gap-1">
          <ChromeIconButton
            ariaLabel={explorerVisible ? "Hide explorer" : "Show explorer"}
            onClick={onToggleExplorer}
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
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-overlay/60 px-4">
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
                id="builder-run-document-select"
                value={selectedDocumentId}
                onChange={(event) => setSelectedDocumentId(event.target.value)}
                className="w-full"
              >
                {documents.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.name}
                  </option>
                ))}
              </Select>
              {selectedDocument ? (
                <p className="text-xs text-muted-foreground">
                  Uploaded {formatDocumentTimestamp(selectedDocument.created_at)} ·{" "}
                  {(selectedDocument.byte_size ?? 0).toLocaleString()} bytes
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="builder-run-log-level-select">
                Log level
              </label>
              <Select
                id="builder-run-log-level-select"
                value={logLevel}
                onChange={(event) => setLogLevel(event.target.value as RunLogLevel)}
                className="w-full"
              >
                {RUN_LOG_LEVEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
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
                            className="h-4 w-4 rounded border-border text-success-600 focus:ring-success-500"
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
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query: { sort: "-created_at", page_size: 50 } },
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
    "text-muted-foreground hover:text-foreground hover:bg-muted hover:border-border-strong focus-visible:ring-ring/40";
  const activeClass = "text-foreground border-border-strong bg-muted";
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
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 via-brand-500 to-brand-600 text-on-brand shadow-[0_12px_24px_rgb(var(--sys-color-shadow)/0.35)]">
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

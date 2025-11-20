import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";

import { ActivityBar, type ActivityBarView } from "./components/ActivityBar";
import { BottomPanel, type WorkbenchRunSummary } from "./components/BottomPanel";
import { EditorArea } from "./components/EditorArea";
import { Explorer } from "./components/Explorer";
import { Inspector } from "./components/Inspector";
import { PanelResizeHandle } from "./components/PanelResizeHandle";
import { useWorkbenchFiles } from "./state/useWorkbenchFiles";
import { useWorkbenchUrlState } from "./state/useWorkbenchUrlState";
import { useUnsavedChangesGuard } from "./state/useUnsavedChangesGuard";
import { useEditorThemePreference } from "./state/useEditorThemePreference";
import type { EditorThemePreference } from "./state/useEditorThemePreference";
import type { WorkbenchConsoleLine, WorkbenchDataSeed, WorkbenchValidationState } from "./types";
import { clamp, trackPointerDrag } from "./utils/drag";
import { createWorkbenchTreeFromListing } from "./utils/tree";

import { ContextMenu, type ContextMenuItem } from "@ui/ContextMenu";
import { SplitButton } from "@ui/SplitButton";
import { PageState } from "@ui/PageState";

import { useConfigFilesQuery, useSaveConfigFileMutation } from "@shared/configs/hooks/useConfigFiles";
import { configsKeys } from "@shared/configs/keys";
import { readConfigFileJson } from "@shared/configs/api";
import type { FileReadJson } from "@shared/configs/types";
import { useValidateConfigurationMutation } from "@shared/configs/hooks/useValidateConfiguration";
import { createScopedStorage } from "@shared/storage";
import type { ConfigBuilderConsole } from "@app/nav/urlState";
import { ApiError } from "@shared/api";
import { streamBuild } from "@shared/builds/api";
import { fetchRunOutputs, streamRun, type RunStreamOptions } from "@shared/runs/api";
import type { RunStatus } from "@shared/runs/types";
import type { components } from "@schema";
import { fetchDocumentSheets, type DocumentSheet } from "@shared/documents";
import { client } from "@shared/api/client";
import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "./utils/console";
import { useNotifications, type NotificationIntent } from "@shared/notifications";
import { Select } from "@ui/Select";
import { Button } from "@ui/Button";
import { Alert } from "@ui/Alert";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const INSPECTOR_LIMITS = { min: 260, max: 420 } as const;
const OUTPUT_LIMITS = { min: 140, max: 420 } as const;
const MIN_EDITOR_HEIGHT = 320;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const MAX_CONSOLE_LINES = 400;
const OUTPUT_HANDLE_THICKNESS = 4; // matches h-1 Tailwind utility on PanelResizeHandle
const ACTIVITY_BAR_WIDTH = 56; // w-14
const CONSOLE_COLLAPSE_MESSAGE =
  "Console closed to keep the editor readable on this screen size. Resize the window or collapse other panes to reopen it.";
const buildTabStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.tabs`;
const buildConsoleStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.console`;
const buildEditorThemeStorageKey = (workspaceId: string, configId: string) =>
  `ade.ui.workspace.${workspaceId}.config.${configId}.editor-theme`;

const THEME_MENU_OPTIONS: Array<{ value: EditorThemePreference; label: string }> = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const ACTIVITY_LABELS: Record<ActivityBarView, string> = {
  explorer: "",
  search: "Search coming soon",
  scm: "Source Control coming soon",
  extensions: "Extensions coming soon",
};

interface ConsolePanelPreferences {
  readonly version: 2;
  readonly fraction: number;
  readonly state: ConfigBuilderConsole;
}

type SideBounds = {
  readonly minPx: number;
  readonly maxPx: number;
  readonly minFrac: number;
  readonly maxFrac: number;
};

type BuildTriggerOptions = {
  readonly force?: boolean;
  readonly wait?: boolean;
  readonly source?: "button" | "menu" | "shortcut";
};

type WorkbenchWindowState = "restored" | "maximized";

type DocumentRecord = components["schemas"]["DocumentOut"];

interface RunStreamMetadata {
  readonly mode: "validation" | "extraction";
  readonly documentId?: string;
  readonly documentName?: string;
  readonly sheetNames?: readonly string[];
}

interface WorkbenchProps {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
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
  seed,
  windowState,
  onMinimizeWindow,
  onMaximizeWindow,
  onRestoreWindow,
  onCloseWorkbench,
  shouldBypassUnsavedGuard,
}: WorkbenchProps) {
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

  const [consoleLines, setConsoleLines] = useState<WorkbenchConsoleLine[]>(() =>
    seed?.console ? seed.console.slice(-MAX_CONSOLE_LINES) : [],
  );

  useEffect(() => {
    if (!seed?.console) {
      return;
    }
    setConsoleLines(seed.console.slice(-MAX_CONSOLE_LINES));
  }, [seed?.console]);

  const [validationState, setValidationState] = useState<WorkbenchValidationState>(() => ({
    status: seed?.validation?.length ? "success" : "idle",
    messages: seed?.validation ?? [],
    lastRunAt: seed?.validation?.length ? new Date().toISOString() : undefined,
    error: null,
    digest: null,
  }));

  const consoleStreamRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  type ActiveStream =
    | {
        readonly kind: "build";
        readonly startedAt: string;
        readonly metadata?: {
          readonly force?: boolean;
          readonly wait?: boolean;
        };
      }
    | {
        readonly kind: "run";
        readonly startedAt: string;
        readonly metadata?: RunStreamMetadata;
      };
  const [activeStream, setActiveStream] = useState<ActiveStream | null>(null);

  const [latestRun, setLatestRun] = useState<WorkbenchRunSummary | null>(null);
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  const resetConsole = useCallback(
    (message: string) => {
      if (!isMountedRef.current) {
        return;
      }
      const timestamp = formatConsoleTimestamp(new Date());
      setConsoleLines([{ level: "info", message, timestamp }]);
    },
    [setConsoleLines],
  );

  const appendConsoleLine = useCallback(
    (line: WorkbenchConsoleLine) => {
      if (!isMountedRef.current) {
        return;
      }
      setConsoleLines((prev) => {
        const next = [...prev, line];
        return next.length > MAX_CONSOLE_LINES ? next.slice(next.length - MAX_CONSOLE_LINES) : next;
      });
    },
    [setConsoleLines],
  );

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

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      consoleStreamRef.current?.abort();
    };
  }, []);

  const validateConfiguration = useValidateConfigurationMutation(workspaceId, configId);

  const tabPersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildTabStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const consolePersistence = useMemo(
    () => (seed ? null : createScopedStorage(buildConsoleStorageKey(workspaceId, configId))),
    [workspaceId, configId, seed],
  );
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | Record<string, unknown> | null>(null);
  if (!initialConsolePrefsRef.current && consolePersistence) {
    initialConsolePrefsRef.current =
      (consolePersistence.get<unknown>() as ConsolePanelPreferences | Record<string, unknown> | null) ?? null;
  }
  const editorTheme = useEditorThemePreference(buildEditorThemeStorageKey(workspaceId, configId));
  const menuAppearance = editorTheme.resolvedTheme === "vs-light" ? "light" : "dark";
  const validationLabel = validationState.lastRunAt ? `Last run ${formatRelative(validationState.lastRunAt)}` : undefined;

  const [explorer, setExplorer] = useState({ collapsed: false, fraction: 280 / 1200 });
  const [inspector, setInspector] = useState({ collapsed: false, fraction: 300 / 1200 });
  const [consoleFraction, setConsoleFraction] = useState<number | null>(null);
  const [hasHydratedConsoleState, setHasHydratedConsoleState] = useState(false);
  const [layoutSize, setLayoutSize] = useState({ width: 0, height: 0 });
  const [paneAreaEl, setPaneAreaEl] = useState<HTMLDivElement | null>(null);
  const [activityView, setActivityView] = useState<ActivityBarView>("explorer");
  const [settingsMenu, setSettingsMenu] = useState<{ x: number; y: number } | null>(null);
  const [buildMenu, setBuildMenu] = useState<{ x: number; y: number } | null>(null);
  const [forceNextBuild, setForceNextBuild] = useState(false);
  const [forceModifierActive, setForceModifierActive] = useState(false);
  const [isResizingConsole, setIsResizingConsole] = useState(false);
  const { notifyBanner, dismissScope } = useNotifications();
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
      if (!isMountedRef.current) {
        return;
      }
      const message = describeError(error);
      appendConsoleLine({ level: "error", message, timestamp: formatConsoleTimestamp(new Date()) });
      showConsoleBanner(message, { intent: "danger", duration: null });
    },
    [appendConsoleLine, showConsoleBanner],
  );

  const isMaximized = windowState === "maximized";
  const isMacPlatform = typeof navigator !== "undefined" ? /mac/i.test(navigator.platform) : false;
  const handleCloseWorkbench = useCallback(() => {
    onCloseWorkbench();
  }, [onCloseWorkbench]);
  const openBuildMenu = useCallback((position: { x: number; y: number }) => {
    setBuildMenu(position);
  }, []);
  const closeBuildMenu = useCallback(() => setBuildMenu(null), []);
  const showExplorerPane = !explorer.collapsed;

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
  const saveConfigFile = useSaveConfigFileMutation(workspaceId, configId);
  const reloadFileFromServer = useCallback(
    async (fileId: string) => {
      if (usingSeed) {
        return null;
      }
      const payload = await queryClient.fetchQuery({
        queryKey: configsKeys.file(workspaceId, configId, fileId),
        queryFn: ({ signal }) => readConfigFileJson(workspaceId, configId, fileId, signal),
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

  const handleToggleForceNextBuild = useCallback(() => {
    setForceNextBuild((current) => !current);
  }, []);
  const outputCollapsed = consoleState !== "open";
  const dirtyTabs = useMemo(
    () => files.tabs.filter((tab) => tab.status === "ready" && tab.content !== tab.initialContent),
    [files.tabs],
  );
  const isSavingTabs = files.tabs.some((tab) => tab.saving);
  const canSaveFiles = !usingSeed && dirtyTabs.length > 0;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [explorer.collapsed, explorer.fraction, inspector.collapsed, inspector.fraction, outputCollapsed, consoleFraction, isMaximized]);

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
      files.beginSavingTab(tabId);
      try {
        const response = await saveConfigFile.mutateAsync({
          path: tab.id,
          content: tab.content,
          etag: tab.etag ?? undefined,
          create: !tab.etag,
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

  const consoleLimits = useMemo(() => {
    const container = Math.max(0, layoutSize.height);
    const maxPx = Math.min(OUTPUT_LIMITS.max, Math.max(0, container - MIN_EDITOR_HEIGHT - OUTPUT_HANDLE_THICKNESS));
    const minPx = Math.min(MIN_CONSOLE_HEIGHT, maxPx);
    return { container, minPx, maxPx };
  }, [layoutSize.height]);

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

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const updateModifierState = (event: KeyboardEvent) => {
      setForceModifierActive(event.shiftKey || event.altKey);
    };
    const resetModifiers = () => setForceModifierActive(false);
    window.addEventListener("keydown", updateModifierState);
    window.addEventListener("keyup", updateModifierState);
    window.addEventListener("blur", resetModifiers);
    return () => {
      window.removeEventListener("keydown", updateModifierState);
      window.removeEventListener("keyup", updateModifierState);
      window.removeEventListener("blur", resetModifiers);
    };
  }, []);

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
      return resolveInitialConsoleFraction();
    });
    return true;
  }, [consoleLimits, setConsole, showConsoleBanner, clearConsoleBanners, resolveInitialConsoleFraction]);

  const closeConsole = useCallback(() => {
    setConsole("closed");
    clearConsoleBanners();
  }, [setConsole, clearConsoleBanners]);

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
  const inspectorBounds = useMemo(
    () => deriveSideBounds(contentWidth, INSPECTOR_LIMITS),
    [contentWidth, deriveSideBounds],
  );

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
    setInspector((prev) => {
      if (prev.collapsed) {
        return prev;
      }
      const next = clampSideFraction(prev.fraction, inspectorBounds);
      return next === prev.fraction ? prev : { ...prev, fraction: next };
    });
  }, [contentWidth, explorerBounds, inspectorBounds, clampSideFraction]);

  const inspectorVisible = !inspector.collapsed && Boolean(files.activeTab);
  const rawExplorerWidth = explorer.collapsed
    ? 0
    : clamp(explorer.fraction, explorerBounds.minFrac, explorerBounds.maxFrac) * contentWidth;
  const rawInspectorWidth = inspectorVisible
    ? clamp(inspector.fraction, inspectorBounds.minFrac, inspectorBounds.maxFrac) * contentWidth
    : 0;
  let explorerWidth = rawExplorerWidth;
  let inspectorWidth = rawInspectorWidth;
  if (contentWidth > 0) {
    const handleBudget =
      (showExplorerPane ? OUTPUT_HANDLE_THICKNESS : 0) + (inspectorVisible ? OUTPUT_HANDLE_THICKNESS : 0);
    const occupied = rawExplorerWidth + rawInspectorWidth + handleBudget;
    if (occupied > contentWidth) {
      const overflow = occupied - contentWidth;
      const inspectorShrink = Math.min(overflow, Math.max(0, rawInspectorWidth - inspectorBounds.minPx));
      inspectorWidth = rawInspectorWidth - inspectorShrink;
      const remaining = overflow - inspectorShrink;
      if (remaining > 0) {
        const explorerShrink = Math.min(remaining, Math.max(0, rawExplorerWidth - explorerBounds.minPx));
        explorerWidth = rawExplorerWidth - explorerShrink;
      }
    }
  }
  const paneHeight = Math.max(0, consoleLimits.container);
  const defaultFraction = 0.25;
  const desiredFraction =
    consoleFraction ??
    (paneHeight > 0 ? clamp(DEFAULT_CONSOLE_HEIGHT / paneHeight, 0, 1) : defaultFraction);
  const desiredHeight = outputCollapsed ? 0 : desiredFraction * paneHeight;
  const consoleHeight = outputCollapsed
    ? 0
    : paneHeight > 0
      ? clampConsoleHeight(desiredHeight)
      : 0;
  const editorHeight =
    paneHeight > 0
      ? Math.max(MIN_EDITOR_HEIGHT, paneHeight - OUTPUT_HANDLE_THICKNESS - consoleHeight)
      : MIN_EDITOR_HEIGHT;

  useEffect(() => {
    const activeId = files.activeTabId;
    if (!activeId) {
      setFileId(undefined);
      return;
    }
    setFileId(activeId);
  }, [files.activeTabId, setFileId]);

  const startRunStream = useCallback(
    (options: RunStreamOptions, metadata: RunStreamMetadata) => {
      if (
        usingSeed ||
        !tree ||
        filesQuery.isLoading ||
        filesQuery.isError ||
        activeStream !== null
      ) {
        return null;
      }
      if (metadata.mode === "validation" && validateConfiguration.isPending) {
        return null;
      }
      if (!openConsole()) {
        return null;
      }

      const startedAt = new Date();
      const startedIso = startedAt.toISOString();
      setPane("console");
      resetConsole(
        metadata.mode === "validation"
          ? "Starting ADE run (validate-only)…"
          : "Starting ADE extraction…",
      );
      if (metadata.mode === "validation") {
        setValidationState((prev) => ({
          ...prev,
          status: "running",
          lastRunAt: startedIso,
          error: null,
        }));
      } else {
        setLatestRun(null);
      }

      const controller = new AbortController();
      consoleStreamRef.current?.abort();
      consoleStreamRef.current = controller;
      setActiveStream({ kind: "run", startedAt: startedIso, metadata });

      void (async () => {
        let currentRunId: string | null = null;
        try {
          for await (const event of streamRun(configId, options, controller.signal)) {
            appendConsoleLine(describeRunEvent(event));
            if (!isMountedRef.current) {
              return;
            }
            if (event.type === "run.created") {
              currentRunId = event.run_id;
            }
            if (event.type === "run.completed") {
              const notice =
                event.status === "succeeded"
                  ? "ADE run completed successfully."
                  : event.status === "canceled"
                    ? "ADE run canceled."
                    : event.error_message?.trim() || "ADE run failed.";
              const intent: NotificationIntent =
                event.status === "succeeded"
                  ? "success"
                  : event.status === "canceled"
                    ? "info"
                    : "danger";
              showConsoleBanner(notice, { intent });

              if (metadata.mode === "extraction" && currentRunId) {
                const downloadBase = `/api/v1/runs/${encodeURIComponent(currentRunId)}`;
                setLatestRun({
                  runId: currentRunId,
                  status: event.status as RunStatus,
                  downloadBase,
                  documentName: metadata.documentName,
                  sheetNames: metadata.sheetNames ?? [],
                  outputs: [],
                  outputsLoaded: false,
                  error: null,
                });
                try {
                  const listing = await fetchRunOutputs(currentRunId);
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, outputs: listing.files, outputsLoaded: true }
                      : prev,
                  );
                } catch (error) {
                  const message =
                    error instanceof Error ? error.message : "Unable to load run outputs.";
                  setLatestRun((prev) =>
                    prev && prev.runId === currentRunId
                      ? { ...prev, outputsLoaded: true, error: message }
                      : prev,
                  );
                }
              }
            }
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          pushConsoleError(error);
        } finally {
          if (consoleStreamRef.current === controller) {
            consoleStreamRef.current = null;
          }
          if (isMountedRef.current) {
            setActiveStream(null);
          }
        }
      })();

      return startedIso;
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      activeStream,
      validateConfiguration.isPending,
      openConsole,
      setPane,
      resetConsole,
      setValidationState,
      setLatestRun,
      consoleStreamRef,
      setActiveStream,
      configId,
      appendConsoleLine,
      showConsoleBanner,
      pushConsoleError,
    ],
  );

  const handleRunValidation = useCallback(() => {
    const startedIso = startRunStream({ validate_only: true }, { mode: "validation" });
    if (!startedIso) {
      return;
    }
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
          lastRunAt: startedIso,
          error: null,
          digest: result.content_digest ?? null,
        });
      },
      onError(error) {
        const message = error instanceof Error ? error.message : "Validation failed.";
        setValidationState({
          status: "error",
          messages: [{ level: "error", message }],
          lastRunAt: startedIso,
          error: message,
          digest: null,
        });
      },
    });
  }, [startRunStream, validateConfiguration, setValidationState]);

  const handleRunExtraction = useCallback(
    (selection: { documentId: string; documentName: string; sheetNames?: readonly string[] }) => {
      const worksheetList = Array.from(new Set((selection.sheetNames ?? []).filter(Boolean)));
      const started = startRunStream(
        {
          input_document_id: selection.documentId,
          input_sheet_names: worksheetList.length ? worksheetList : undefined,
          input_sheet_name: worksheetList.length === 1 ? worksheetList[0] : undefined,
        },
        {
          mode: "extraction",
          documentId: selection.documentId,
          documentName: selection.documentName,
          sheetNames: worksheetList,
        },
      );
      if (started) {
        setRunDialogOpen(false);
      }
    },
    [startRunStream],
  );

  const triggerBuild = useCallback(
    (options?: BuildTriggerOptions) => {
      closeBuildMenu();
      if (
        usingSeed ||
        !tree ||
        filesQuery.isLoading ||
        filesQuery.isError ||
        activeStream !== null
      ) {
        return;
      }
      if (!openConsole()) {
        return;
      }

      const resolvedForce = typeof options?.force === "boolean" ? options.force : forceModifierActive;
      const resolvedWait = Boolean(options?.wait);

      const startedIso = new Date().toISOString();
      setPane("console");
      resetConsole(resolvedForce ? "Force rebuilding environment…" : "Starting configuration build…");

      const nowTimestamp = formatConsoleTimestamp(new Date());
      if (resolvedForce) {
        appendConsoleLine({
          level: "warning",
          message: "Force rebuild requested. ADE will recreate the environment from scratch.",
          timestamp: nowTimestamp,
        });
      } else if (resolvedWait) {
        appendConsoleLine({
          level: "info",
          message: "Waiting for any running build to finish before starting.",
          timestamp: nowTimestamp,
        });
      }

      const controller = new AbortController();
      consoleStreamRef.current?.abort();
      consoleStreamRef.current = controller;
      setActiveStream({
        kind: "build",
        startedAt: startedIso,
        metadata: { force: resolvedForce, wait: resolvedWait },
      });

      void (async () => {
        try {
          for await (const event of streamBuild(
            workspaceId,
            configId,
            { force: resolvedForce, wait: resolvedWait },
            controller.signal,
          )) {
            appendConsoleLine(describeBuildEvent(event));
            if (!isMountedRef.current) {
              return;
            }
            if (event.type === "build.completed") {
              const summary = event.summary?.trim();
              if (summary && /reused/i.test(summary)) {
                appendConsoleLine({
                  level: "info",
                  message: "Environment reused. Hold Shift or open the build menu to force a rebuild.",
                  timestamp: formatConsoleTimestamp(new Date()),
                });
                showConsoleBanner(
                  "Environment already up to date. Hold Shift or use the menu to force rebuild.",
                  { intent: "info" },
                );
              } else {
                const notice =
                  event.status === "active"
                    ? summary || "Build completed successfully."
                    : event.status === "canceled"
                      ? "Build canceled."
                      : event.error_message?.trim() || "Build failed.";
                const intent: NotificationIntent =
                  event.status === "active"
                    ? "success"
                    : event.status === "canceled"
                      ? "info"
                      : "danger";
                showConsoleBanner(notice, { intent });
              }
            }
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          pushConsoleError(error);
        } finally {
          if (consoleStreamRef.current === controller) {
            consoleStreamRef.current = null;
          }
          if (isMountedRef.current) {
            setActiveStream(null);
          }
        }
      })();
    },
    [
      usingSeed,
      tree,
      filesQuery.isLoading,
      filesQuery.isError,
      activeStream,
      closeBuildMenu,
      openConsole,
      forceModifierActive,
      setPane,
      resetConsole,
      appendConsoleLine,
      consoleStreamRef,
      setActiveStream,
      workspaceId,
      configId,
      pushConsoleError,
      showConsoleBanner,
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
      if (event.key.toLowerCase() !== "b") {
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName;
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          (target as HTMLElement).isContentEditable
        ) {
          return;
        }
      }
      event.preventDefault();
      triggerBuild({ force: event.shiftKey, source: "shortcut" });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [triggerBuild, isMacPlatform]);

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

  const runStreamMetadata = activeStream?.kind === "run" ? activeStream.metadata : undefined;
  const isStreamingRun = activeStream?.kind === "run";
  const isStreamingBuild = activeStream?.kind === "build";
  const isStreamingAny = activeStream !== null;

  const isStreamingExtraction = isStreamingRun && runStreamMetadata?.mode === "extraction";
  const isStreamingValidationRun = isStreamingRun && runStreamMetadata?.mode !== "extraction";

  const isRunningValidation =
    validationState.status === "running" || validateConfiguration.isPending || isStreamingValidationRun;
  const canRunValidation =
    !usingSeed &&
    Boolean(tree) &&
    !filesQuery.isLoading &&
    !filesQuery.isError &&
    !isStreamingAny &&
    !validateConfiguration.isPending &&
    validationState.status !== "running";

  const isRunningExtraction = isStreamingExtraction;
  const canRunExtraction =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isStreamingAny;

  const isBuildingEnvironment = isStreamingBuild;
  const canBuildEnvironment =
    !usingSeed && Boolean(tree) && !filesQuery.isLoading && !filesQuery.isError && !isStreamingAny;

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

  const closeSettingsMenu = useCallback(() => setSettingsMenu(null), []);

  const handleToggleOutput = useCallback(() => {
    if (outputCollapsed) {
      void openConsole();
    } else {
      closeConsole();
    }
  }, [outputCollapsed, openConsole, closeConsole]);

  const handleToggleExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const handleHideExplorer = useCallback(() => {
    setExplorer((prev) => ({ ...prev, collapsed: true }));
  }, []);

  const handleToggleInspectorVisibility = useCallback(() => {
    setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed }));
  }, []);

  const settingsMenuItems = useMemo<ContextMenuItem[]>(() => {
    const blankIcon = <span className="inline-block h-4 w-4 opacity-0" />;
    const items: ContextMenuItem[] = THEME_MENU_OPTIONS.map((option) => ({
      id: `theme-${option.value}`,
      label: `${option.label} theme`,
      icon: editorTheme.preference === option.value ? <MenuIconCheck /> : blankIcon,
      onSelect: () => editorTheme.setPreference(option.value),
    }));
    items.push(
      {
        id: "toggle-explorer",
        label: explorer.collapsed ? "Show Explorer" : "Hide Explorer",
        dividerAbove: true,
        icon: explorer.collapsed ? blankIcon : <MenuIconCheck />,
        onSelect: () => setExplorer((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-inspector",
        label: inspector.collapsed ? "Show Inspector" : "Hide Inspector",
        icon: inspector.collapsed ? blankIcon : <MenuIconCheck />,
        onSelect: () => setInspector((prev) => ({ ...prev, collapsed: !prev.collapsed })),
      },
      {
        id: "toggle-console",
        label: outputCollapsed ? "Show Console" : "Hide Console",
        icon: outputCollapsed ? blankIcon : <MenuIconCheck />,
        onSelect: handleToggleOutput,
      },
    );
    return items;
  }, [
    editorTheme,
    explorer.collapsed,
    inspector.collapsed,
    outputCollapsed,
    handleToggleOutput,
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
  const buildShortcutLabel = isMacPlatform ? "⌘B" : "Ctrl+B";
  const forceShortcutLabel = isMacPlatform ? "⇧⌘B" : "Ctrl+Shift+B";
  const buildMenuItems = useMemo<ContextMenuItem[]>(() => {
    const disabled = !canBuildEnvironment;
    return [
      {
        id: "build-default",
        label: "Build / reuse environment",
        shortcut: buildShortcutLabel,
        disabled,
        onSelect: () => triggerBuild(),
      },
      {
        id: "build-force",
        label: "Force rebuild now",
        shortcut: forceShortcutLabel,
        disabled,
        onSelect: () => triggerBuild({ force: true }),
      },
      {
        id: "build-force-wait",
        label: "Force rebuild after current build",
        disabled,
        onSelect: () => triggerBuild({ force: true, wait: true }),
      },
    ];
  }, [buildShortcutLabel, forceShortcutLabel, canBuildEnvironment, triggerBuild]);

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
  const rootSurfaceClass = isMaximized
    ? menuAppearance === "dark"
      ? "bg-[#0f111a] text-white"
      : "bg-slate-50 text-slate-900"
    : menuAppearance === "dark"
      ? "bg-transparent text-white"
      : "bg-transparent text-slate-900";
  const editorSurface = menuAppearance === "dark" ? "#1b1f27" : "#ffffff";
  const editorText = menuAppearance === "dark" ? "#f5f6fb" : "#0f172a";
  const windowFrameClass = isMaximized
    ? clsx(
        "fixed inset-0 z-[90] flex flex-col",
        menuAppearance === "dark" ? "bg-[#0f111a] text-white" : "bg-white text-slate-900",
      )
    : clsx(
        "flex w-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
        menuAppearance === "dark" ? "bg-[#101322] text-white" : "bg-white text-slate-900",
      );

  return (
    <div className={clsx("flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden", rootSurfaceClass)}>
      {isMaximized ? <div className="fixed inset-0 z-40 bg-slate-900/60" /> : null}
      <div className={windowFrameClass}>
        <WorkbenchChrome
        configName={configName}
        workspaceLabel={workspaceLabel}
        validationLabel={validationLabel}
        canSaveFiles={canSaveFiles}
        isSavingFiles={isSavingTabs}
        onSaveFile={handleSaveActiveTab}
        saveShortcutLabel={saveShortcutLabel}
        canBuildEnvironment={canBuildEnvironment}
        isBuildingEnvironment={isBuildingEnvironment}
        onBuildEnvironment={triggerBuild}
        onOpenBuildMenu={openBuildMenu}
        forceModifierActive={forceModifierActive}
        buildShortcutLabel={buildShortcutLabel}
        forceShortcutLabel={forceShortcutLabel}
        canRunValidation={canRunValidation}
        isRunningValidation={isRunningValidation}
        onRunValidation={handleRunValidation}
        canRunExtraction={canRunExtraction}
        isRunningExtraction={isRunningExtraction}
        onRunExtraction={() => {
          if (!canRunExtraction) {
            return;
          }
          setRunDialogOpen(true);
        }}
        explorerVisible={showExplorerPane}
        onToggleExplorer={handleToggleExplorer}
        consoleOpen={!outputCollapsed}
        onToggleConsole={handleToggleOutput}
        inspectorCollapsed={inspector.collapsed}
        onToggleInspector={handleToggleInspectorVisibility}
        appearance={menuAppearance}
        forceNextBuild={forceNextBuild}
        onToggleForceNextBuild={handleToggleForceNextBuild}
        windowState={windowState}
        onMinimizeWindow={handleMinimizeWindow}
        onToggleMaximize={handleToggleMaximize}
        onCloseWindow={handleCloseWorkbench}
      />
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
                    onCloseFile={files.closeTab}
                    onCloseOtherFiles={files.closeOtherTabs}
                    onCloseTabsToRight={files.closeTabsToRight}
                    onCloseAllFiles={files.closeAllTabs}
                    onHide={handleHideExplorer}
                  />
                ) : (
                  <SidePanelPlaceholder width={explorerWidth} view={activityView} />
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

        <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={{ backgroundColor: editorSurface, color: editorText }}>
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
              onSaveTab={handleSaveTabShortcut}
              onSaveAllTabs={handleSaveAllTabs}
              onMoveTab={files.moveTab}
              onPinTab={files.pinTab}
              onUnpinTab={files.unpinTab}
              onSelectRecentTab={files.selectRecentTab}
              editorTheme={editorTheme.resolvedTheme}
              menuAppearance={menuAppearance}
              canSaveFiles={canSaveFiles}
              minHeight={MIN_EDITOR_HEIGHT}
            />
          ) : (
            <div
                className="grid min-h-0 min-w-0 flex-1"
                style={{
                height: paneHeight > 0 ? `${paneHeight}px` : undefined,
                gridTemplateRows: `${Math.max(MIN_EDITOR_HEIGHT, editorHeight)}px ${OUTPUT_HANDLE_THICKNESS}px ${Math.max(
                  0,
                  consoleHeight,
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
                onSaveTab={handleSaveTabShortcut}
                onSaveAllTabs={handleSaveAllTabs}
                onMoveTab={files.moveTab}
                onPinTab={files.pinTab}
                onUnpinTab={files.unpinTab}
                onSelectRecentTab={files.selectRecentTab}
                editorTheme={editorTheme.resolvedTheme}
                menuAppearance={menuAppearance}
                canSaveFiles={canSaveFiles}
                minHeight={MIN_EDITOR_HEIGHT}
              />
              <PanelResizeHandle
                orientation="horizontal"
                onPointerDown={(event) => {
                  setIsResizingConsole(true);
                  const startY = event.clientY;
                  const startHeight = consoleHeight;
                  trackPointerDrag(event, {
                    cursor: "row-resize",
                    onMove: (move) => {
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
              />
              <BottomPanel
                height={Math.max(0, consoleHeight)}
                consoleLines={consoleLines}
                validation={validationState}
                activePane={pane}
                onPaneChange={setPane}
                latestRun={latestRun}
              />
            </div>
          )}
        </div>

        {inspectorVisible ? (
          <>
            <PanelResizeHandle
              orientation="vertical"
              onPointerDown={(event) => {
                const startX = event.clientX;
                const startWidth = inspectorWidth;
                trackPointerDrag(event, {
                  cursor: "col-resize",
                  onMove: (move) => {
                    const delta = startX - move.clientX;
                    const nextWidth = clamp(startWidth + delta, inspectorBounds.minPx, inspectorBounds.maxPx);
                    setInspector((prev) =>
                      prev.collapsed || contentWidth <= 0
                        ? prev
                        : { ...prev, fraction: clampSideFraction(nextWidth / contentWidth, inspectorBounds) },
                    );
                  },
                });
              }}
            />
            <Inspector width={inspectorWidth} file={files.activeTab} />
          </>
        ) : null}
      </div>
      </div>
      {runDialogOpen ? (
        <RunExtractionDialog
          open={runDialogOpen}
          workspaceId={workspaceId}
          onClose={() => setRunDialogOpen(false)}
          onRun={handleRunExtraction}
        />
      ) : null}
      <ContextMenu
        open={Boolean(buildMenu)}
        position={buildMenu ?? undefined}
        onClose={closeBuildMenu}
        items={buildMenuItems}
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
}

function SidePanelPlaceholder({ width, view }: SidePanelPlaceholderProps) {
  const label = ACTIVITY_LABELS[view] || "Coming soon";
  return (
    <div
      className="flex h-full min-h-0 flex-col items-center justify-center border-r border-[#111111] bg-[#1e1e1e] px-4 text-center text-[11px] uppercase tracking-wide text-slate-400"
      style={{ width }}
      aria-live="polite"
    >
      {label}
    </div>
  );
}

function MenuIconCheck() {
  return (
    <svg className="h-4 w-4 text-[#4fc1ff]" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 8l3 3 5-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
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
  canBuildEnvironment,
  isBuildingEnvironment,
  onBuildEnvironment,
  onOpenBuildMenu,
  forceNextBuild,
  forceModifierActive,
  buildShortcutLabel,
  forceShortcutLabel,
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
  inspectorCollapsed,
  onToggleInspector,
  appearance,
  windowState,
  onMinimizeWindow,
  onToggleMaximize,
  onCloseWindow,
}: {
  readonly configName: string;
  readonly workspaceLabel: string;
  readonly validationLabel?: string;
  readonly canSaveFiles: boolean;
  readonly isSavingFiles: boolean;
  readonly onSaveFile: () => void;
  readonly saveShortcutLabel: string;
  readonly canBuildEnvironment: boolean;
  readonly isBuildingEnvironment: boolean;
  readonly onBuildEnvironment: (options?: BuildTriggerOptions) => void;
  readonly onOpenBuildMenu: (position: { x: number; y: number }) => void;
  readonly forceNextBuild: boolean;
  readonly forceModifierActive: boolean;
  readonly buildShortcutLabel: string;
  readonly forceShortcutLabel: string;
  readonly canRunValidation: boolean;
  readonly isRunningValidation: boolean;
  readonly onRunValidation: () => void;
  readonly canRunExtraction: boolean;
  readonly isRunningExtraction: boolean;
  readonly onRunExtraction: () => void;
  readonly explorerVisible: boolean;
  readonly onToggleExplorer: () => void;
  readonly consoleOpen: boolean;
  readonly onToggleConsole: () => void;
  readonly inspectorCollapsed: boolean;
  readonly onToggleInspector: () => void;
  readonly appearance: "light" | "dark";
  readonly windowState: WorkbenchWindowState;
  readonly onMinimizeWindow: () => void;
  readonly onToggleMaximize: () => void;
  readonly onCloseWindow: () => void;
}) {
  const dark = appearance === "dark";
  const surfaceClass = dark
    ? "border-white/10 bg-[#151821] text-white"
    : "border-slate-200 bg-white text-slate-900";
  const metaTextClass = dark ? "text-white/60" : "text-slate-500";
  const buildButtonClass = dark
    ? "bg-white/10 text-white hover:bg-white/20 disabled:bg-white/10 disabled:text-white/40"
    : "bg-slate-100 text-slate-900 hover:bg-slate-200 disabled:bg-slate-50 disabled:text-slate-400";
  const saveButtonClass = dark
    ? "bg-emerald-400/20 text-emerald-50 hover:bg-emerald-400/30 disabled:bg-white/10 disabled:text-white/30"
    : "bg-emerald-500 text-white hover:bg-emerald-400 disabled:bg-slate-200 disabled:text-slate-500";
  const runButtonClass = dark
    ? "bg-brand-500 text-white hover:bg-brand-400 disabled:bg-white/20 disabled:text-white/40"
    : "bg-brand-600 text-white hover:bg-brand-500 disabled:bg-slate-200 disabled:text-slate-500";
  const isMaximized = windowState === "maximized";
  const forceIntentActive = forceNextBuild || forceModifierActive;
  const buildButtonLabel = isBuildingEnvironment
    ? "Building…"
    : forceIntentActive
      ? "Force rebuild"
      : "Build environment";
  const buildButtonTitle = forceIntentActive
    ? `Force rebuild (Shift+Click · ${forceShortcutLabel})`
    : `Build environment (${buildShortcutLabel})`;

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
          {isSavingFiles ? <SpinnerIcon /> : <SaveIcon />}
          {isSavingFiles ? "Saving…" : "Save"}
        </button>
        <SplitButton
          label={buildButtonLabel}
          icon={isBuildingEnvironment ? <SpinnerIcon /> : <BuildIcon />}
          disabled={!canBuildEnvironment}
          isLoading={isBuildingEnvironment}
          highlight={forceIntentActive && !isBuildingEnvironment}
          title={buildButtonTitle}
          primaryClassName={clsx(
            buildButtonClass,
            "rounded-r-none focus-visible:ring-offset-0",
          )}
          menuClassName={clsx(
            buildButtonClass,
            "rounded-l-none px-2",
            dark ? "border-white/20" : "border-slate-300",
          )}
          menuAriaLabel="Open build options"
          onPrimaryClick={(event) =>
            onBuildEnvironment({
              force: event.shiftKey || event.altKey || forceModifierActive,
            })
          }
          onOpenMenu={(position) => onOpenBuildMenu({ x: position.x, y: position.y })}
          onContextMenu={(event) => {
            event.preventDefault();
            onOpenBuildMenu({ x: event.clientX, y: event.clientY });
          }}
        />
        <button
          type="button"
          onClick={onRunValidation}
          disabled={!canRunValidation}
          className={clsx(
            "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-0",
            runButtonClass,
          )}
        >
          {isRunningValidation ? <SpinnerIcon /> : <RunIcon />}
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
        >
          {isRunningExtraction ? <SpinnerIcon /> : <RunIcon />}
          {isRunningExtraction ? "Running…" : "Run extraction"}
        </button>
        <div className="flex items-center gap-1">
          <ChromeIconButton
            ariaLabel={explorerVisible ? "Hide explorer" : "Show explorer"}
            onClick={onToggleExplorer}
            appearance={appearance}
            active={explorerVisible}
            icon={<SidebarIcon active={explorerVisible} />}
          />
          <ChromeIconButton
            ariaLabel={inspectorCollapsed ? "Show inspector" : "Hide inspector"}
            onClick={onToggleInspector}
            appearance={appearance}
            active={!inspectorCollapsed}
            icon={<InspectorIcon />}
          />
          <ChromeIconButton
            ariaLabel={consoleOpen ? "Hide console" : "Show console"}
            onClick={onToggleConsole}
            appearance={appearance}
            active={consoleOpen}
            icon={<ConsoleIcon />}
          />
        </div>
        <div
          className={clsx(
            "flex items-center gap-2 border-l pl-3",
            appearance === "dark" ? "border-white/20" : "border-slate-200/70",
          )}
        >
          <ChromeIconButton
            ariaLabel="Minimize workbench"
            onClick={onMinimizeWindow}
            appearance={appearance}
            icon={<MinimizeIcon />}
          />
          <ChromeIconButton
            ariaLabel={isMaximized ? "Restore workbench" : "Maximize workbench"}
            onClick={onToggleMaximize}
            appearance={appearance}
            active={isMaximized}
            icon={isMaximized ? <WindowRestoreIcon /> : <WindowMaximizeIcon />}
          />
          <ChromeIconButton
            ariaLabel="Close workbench"
            onClick={onCloseWindow}
            appearance={appearance}
            icon={<CloseIcon />}
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
  }) => void;
}

function RunExtractionDialog({ open, workspaceId, onClose, onRun }: RunExtractionDialogProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const documentsQuery = useQuery<DocumentRecord[]>({
    queryKey: ["builder-documents", workspaceId],
    queryFn: ({ signal }) => fetchRecentDocuments(workspaceId, signal),
    staleTime: 60_000,
  });
  const documents = useMemo(
    () => documentsQuery.data ?? [],
    [documentsQuery.data],
  );
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>("");
  useEffect(() => {
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
  }, [documents]);

  const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId) ?? null;
  const sheetQuery = useQuery<DocumentSheet[]>({
    queryKey: ["builder-document-sheets", workspaceId, selectedDocumentId],
    queryFn: ({ signal }) => fetchDocumentSheets(workspaceId, selectedDocumentId, signal),
    enabled: Boolean(selectedDocumentId),
    staleTime: 60_000,
  });
  const sheetOptions = useMemo(
    () => sheetQuery.data ?? [],
    [sheetQuery.data],
  );
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  useEffect(() => {
    if (!sheetOptions.length) {
      setSelectedSheets([]);
      return;
    }
    setSelectedSheets((current) =>
      current.filter((name) => sheetOptions.some((sheet) => sheet.name === name)),
    );
  }, [sheetOptions]);

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
    <div className="fixed inset-0 z-[95] flex items-center justify-center bg-slate-900/60 px-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-2xl"
      >
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Select a document</h2>
            <p className="text-sm text-slate-500">
              Choose a workspace document and optional worksheet before running the extractor.
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </header>

        {documentsQuery.isError ? (
          <Alert tone="danger">Unable to load documents. Try again later.</Alert>
        ) : documentsQuery.isLoading ? (
          <p className="text-sm text-slate-500">Loading documents…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-slate-500">Upload a document in the workspace to run the extractor.</p>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="builder-run-document-select">
                Document
              </label>
              <Select
                id="builder-run-document-select"
                value={selectedDocumentId}
                onChange={(event) => setSelectedDocumentId(event.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              >
                {documents.map((document) => (
                  <option key={document.id} value={document.id}>
                    {document.name}
                  </option>
                ))}
              </Select>
              {selectedDocument ? (
                <p className="text-xs text-slate-500">
                  Uploaded {formatDocumentTimestamp(selectedDocument.created_at)} ·{" "}
                  {(selectedDocument.byte_size ?? 0).toLocaleString()} bytes
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Worksheet</p>
              {sheetQuery.isLoading ? (
                <p className="text-sm text-slate-500">Loading worksheets…</p>
              ) : sheetQuery.isError ? (
                <Alert tone="warning">
                  <div className="space-y-2">
                    <p className="text-sm text-slate-700">
                      Worksheet metadata is temporarily unavailable. The run will process the entire file unless you retry and
                      pick specific sheets.
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => sheetQuery.refetch()}
                        disabled={sheetQuery.isFetching}
                      >
                        Retry loading
                      </Button>
                      <Button variant="ghost" size="xs" onClick={() => setSelectedSheets([])}>
                        Use all worksheets
                      </Button>
                    </div>
                  </div>
                </Alert>
              ) : sheetsAvailable ? (
                <div className="space-y-3 rounded-lg border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-slate-700">Worksheets</p>
                      <p className="text-xs text-slate-500">
                        {normalizedSheetSelection.length === 0
                          ? "All worksheets will be processed by default. Select specific sheets to narrow the run."
                          : `${normalizedSheetSelection.length.toLocaleString()} worksheet${
                              normalizedSheetSelection.length === 1 ? "" : "s"
                            } selected.`}
                      </p>
                    </div>
                    <Button variant="ghost" size="xs" onClick={() => setSelectedSheets([])}>
                      Use all worksheets
                    </Button>
                  </div>

                  <div className="max-h-48 space-y-2 overflow-auto rounded-md border border-slate-200 p-2">
                    {sheetOptions.map((sheet) => {
                      const checked = normalizedSheetSelection.includes(sheet.name);
                      return (
                        <label
                          key={`${sheet.index}-${sheet.name}`}
                          className="flex items-center gap-2 rounded px-2 py-1 text-sm text-slate-700 hover:bg-slate-100"
                        >
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
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
                <p className="text-sm text-slate-500">This file will be ingested directly.</p>
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
                  sheetNames:
                    normalizedSheetSelection.length > 0 ? normalizedSheetSelection : undefined,
                });
              }}
              disabled={runDisabled}
            >
              Run extraction
          </Button>
        </footer>
      </div>
    </div>
  );

  return typeof document === "undefined" ? null : createPortal(content, document.body);
}

async function fetchRecentDocuments(workspaceId: string, signal?: AbortSignal): Promise<DocumentRecord[]> {
  const { data } = await client.GET("/api/v1/workspaces/{workspace_id}/documents", {
    params: { path: { workspace_id: workspaceId }, query: { sort: "-created_at", page_size: 50 } },
    signal,
  });
  return ((data as components["schemas"]["DocumentPage"] | undefined)?.items ?? []) as DocumentRecord[];
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
  appearance,
  active = false,
}: {
  readonly ariaLabel: string;
  readonly onClick: () => void;
  readonly icon: JSX.Element;
  readonly appearance: "light" | "dark";
  readonly active?: boolean;
}) {
  const dark = appearance === "dark";
  const baseClass = dark
    ? "text-white/70 hover:text-white hover:bg-white/5 hover:border-white/20 focus-visible:ring-white/40"
    : "text-slate-500 hover:text-slate-900 hover:bg-slate-100 hover:border-slate-300 focus-visible:ring-slate-400/40";
  const activeClass = dark ? "text-white border-white/30 bg-white/10" : "text-slate-900 border-slate-300 bg-slate-200/70";
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={clsx(
        "flex h-7 w-7 items-center justify-center rounded-[4px] border border-transparent text-sm transition focus-visible:outline-none focus-visible:ring-2",
        baseClass,
        active && activeClass,
      )}
      title={ariaLabel}
    >
      {icon}
    </button>
  );
}

function WorkbenchBadgeIcon() {
  return (
    <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#4fc1ff] via-[#2d7dff] to-[#7c4dff] text-white shadow-lg shadow-[#10121f]">
      <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="9" y="2" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="2" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
        <rect x="9" y="9" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.2" />
      </svg>
    </span>
  );
}

function SidebarIcon({ active }: { readonly active: boolean }) {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect
        x="3"
        y="4"
        width="14"
        height="12"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.4"
        opacity={active ? 1 : 0.6}
      />
      <path d="M7 4v12" stroke="currentColor" strokeWidth="1.4" opacity={active ? 1 : 0.6} />
    </svg>
  );
}

function ConsoleIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M3 10.5h10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function InspectorIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.2" />
      <path d="M10 3v10" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function WindowMaximizeIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="3" y="3" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function WindowRestoreIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 5.5h6v6h-6z" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 4h6v6" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function MinimizeIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4 11h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" opacity="0.35" />
      <path d="M20 12a8 8 0 0 0-8-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function BuildIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M11 2.5a2.5 2.5 0 0 0-2.62 3.04L4 9.92 6.08 12l4.58-4.38A2.5 2.5 0 0 0 13.5 5 2.5 2.5 0 0 0 11 2.5Z"
        fill="currentColor"
      />
      <path d="M4 10l2 2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

function RunIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 3.5v9l7-4.5-7-4.5Z" fill="currentColor" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M4 2.5h7.25L13.5 4.8v8.7H4z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Operation canceled.";
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

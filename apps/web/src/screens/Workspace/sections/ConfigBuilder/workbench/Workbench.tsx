import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import clsx from "clsx";
import { useQueryClient } from "@tanstack/react-query";

import { ActivityBar, type ActivityBarView } from "./components/ActivityBar";
import { BottomPanel } from "./components/BottomPanel";
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
import { streamRun } from "@shared/runs/api";
import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "./utils/console";
import { useNotifications, type NotificationIntent } from "@shared/notifications";

const EXPLORER_LIMITS = { min: 200, max: 420 } as const;
const INSPECTOR_LIMITS = { min: 260, max: 420 } as const;
const OUTPUT_LIMITS = { min: 140, max: 420 } as const;
const MIN_EDITOR_HEIGHT = 320;
const MIN_CONSOLE_HEIGHT = 140;
const DEFAULT_CONSOLE_HEIGHT = 220;
const MAX_CONSOLE_LINES = 400;
const OUTPUT_HANDLE_THICKNESS = 4; // matches h-1 Tailwind utility on PanelResizeHandle
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
  readonly height: number;
  readonly state: ConfigBuilderConsole;
}

type BuildTriggerOptions = {
  readonly force?: boolean;
  readonly wait?: boolean;
  readonly source?: "button" | "menu" | "shortcut";
};

type WorkbenchWindowState = "restored" | "maximized";

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
  const [activeStream, setActiveStream] = useState<null | {
    readonly kind: "build" | "run";
    readonly startedAt: string;
    readonly metadata?: {
      readonly force?: boolean;
      readonly wait?: boolean;
    };
  }>(null);

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
  const initialConsolePrefsRef = useRef<ConsolePanelPreferences | null>(null);
  if (!initialConsolePrefsRef.current && consolePersistence) {
    initialConsolePrefsRef.current = consolePersistence.get<ConsolePanelPreferences>() ?? null;
  }
  const editorTheme = useEditorThemePreference(buildEditorThemeStorageKey(workspaceId, configId));
  const menuAppearance = editorTheme.resolvedTheme === "vs-light" ? "light" : "dark";
  const validationLabel = validationState.lastRunAt ? `Last run ${formatRelative(validationState.lastRunAt)}` : undefined;

  const [explorer, setExplorer] = useState({ collapsed: false, width: 280 });
  const [inspector, setInspector] = useState({ collapsed: false, width: 300 });
  const [outputHeight, setOutputHeight] = useState(
    () => initialConsolePrefsRef.current?.height ?? DEFAULT_CONSOLE_HEIGHT,
  );
  const [hasHydratedConsoleState, setHasHydratedConsoleState] = useState(false);
  const [centerPaneEl, setCenterPaneEl] = useState<HTMLDivElement | null>(null);
  const [centerHeight, setCenterHeight] = useState(0);
  const [hasMeasuredCenter, setHasMeasuredCenter] = useState(false);
  const [activityView, setActivityView] = useState<ActivityBarView>("explorer");
  const [settingsMenu, setSettingsMenu] = useState<{ x: number; y: number } | null>(null);
  const [buildMenu, setBuildMenu] = useState<{ x: number; y: number } | null>(null);
  const [forceNextBuild, setForceNextBuild] = useState(false);
  const [forceModifierActive, setForceModifierActive] = useState(false);
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
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new Event("ade:workbench-layout"));
    });
  }, [explorer.collapsed, explorer.width, inspector.collapsed, inspector.width, outputCollapsed, outputHeight, isMaximized]);

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
        const concurrencyMessage =
          "Save blocked because this file changed on the server. Reload the latest version to continue.";
        const failure =
          error instanceof ApiError && error.status === 412 ? new Error(concurrencyMessage) : error;
        files.failSavingTab(tabId, failure instanceof Error ? failure.message : String(failure));
        pushConsoleError(failure);
        return false;
      }
    },
    [
      usingSeed,
      files.tabs,
      files.beginSavingTab,
      files.completeSavingTab,
      files.failSavingTab,
      saveConfigFile,
      showConsoleBanner,
      pushConsoleError,
    ],
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
    if (consoleBounds.hasMeasurement && !consoleBounds.canFitMin) {
      setConsole("closed");
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return false;
    }
    clearConsoleBanners();
    setConsole("open");
    setOutputHeight((current) => clampOutputHeight(current > 0 ? current : DEFAULT_CONSOLE_HEIGHT));
    return true;
  }, [consoleBounds, clampOutputHeight, setConsole, showConsoleBanner, clearConsoleBanners]);

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
      showConsoleBanner(CONSOLE_COLLAPSE_MESSAGE, { intent: "warning", duration: 10000 });
      return;
    }
    setOutputHeight((current) => clampOutputHeight(current));
  }, [consoleState, consoleBounds, clampOutputHeight, setConsole, showConsoleBanner]);

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
      !tree ||
      filesQuery.isLoading ||
      filesQuery.isError ||
      activeStream !== null ||
      validateConfiguration.isPending
    ) {
      return;
    }
    if (!openConsole()) {
      return;
    }

    const startedAt = new Date();
    const startedIso = startedAt.toISOString();
    setPane("console");
    resetConsole("Starting ADE run (validate-only)…");
    setValidationState((prev) => ({
      ...prev,
      status: "running",
      lastRunAt: startedIso,
      error: null,
    }));

    const controller = new AbortController();
    consoleStreamRef.current?.abort();
    consoleStreamRef.current = controller;
    setActiveStream({ kind: "run", startedAt: startedIso });

    void (async () => {
      try {
        for await (const event of streamRun(configId, { validate_only: true }, controller.signal)) {
          appendConsoleLine(describeRunEvent(event));
          if (!isMountedRef.current) {
            return;
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
  }, [
    usingSeed,
    tree,
    filesQuery.isLoading,
    filesQuery.isError,
    activeStream,
    validateConfiguration,
    openConsole,
    setPane,
    resetConsole,
    consoleStreamRef,
    setActiveStream,
    streamRun,
    configId,
    appendConsoleLine,
    pushConsoleError,
    showConsoleBanner,
  ]);

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
      streamBuild,
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

  const isStreamingRun = activeStream?.kind === "run";
  const isStreamingBuild = activeStream?.kind === "build";
  const isStreamingAny = activeStream !== null;

  const isRunningValidation =
    validationState.status === "running" || validateConfiguration.isPending || isStreamingRun;
  const canRunValidation =
    !usingSeed &&
    Boolean(tree) &&
    !filesQuery.isLoading &&
    !filesQuery.isError &&
    !isStreamingAny &&
    !validateConfiguration.isPending &&
    validationState.status !== "running";

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
    editorTheme.preference,
    editorTheme.setPreference,
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
        <div className="flex min-h-0 min-w-0 flex-1">
          <ActivityBar
            activeView={activityView}
            onSelectView={handleSelectActivityView}
            onOpenSettings={handleOpenSettingsMenu}
            appearance={menuAppearance}
          />
          {showExplorerPane ? (
            <>
              <div className="flex min-h-0" style={{ width: explorer.width }}>
                {activityView === "explorer" && files.tree ? (
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
                    onHide={handleHideExplorer}
                  />
                ) : (
                  <SidePanelPlaceholder width={explorer.width} view={activityView} />
                )}
              </div>
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

        <div
          ref={setCenterPaneEl}
          className="flex min-h-0 min-w-0 flex-1 flex-col"
          style={{ backgroundColor: editorSurface, color: editorText }}
        >
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

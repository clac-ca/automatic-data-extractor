import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "react-router-dom";

import { Workbench } from "@pages/Workspace/sections/ConfigBuilder/workbench/Workbench";
import type { WorkbenchDataSeed } from "@pages/Workspace/sections/ConfigBuilder/workbench/types";
import { getWorkbenchReturnPathStorageKey } from "@pages/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState";

import { createScopedStorage } from "@lib/storage";
import {
  SearchParamsOverrideProvider,
  toURLSearchParams,
  type SetSearchParamsInit,
} from "@app/navigation/urlState";
import { DockCloseIcon, DockRestoreIcon, DockWindowIcon } from "@components/icons";

type WorkbenchWindowState = "restored" | "maximized" | "minimized";

interface WorkbenchSessionPayload {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly configDisplayName: string;
  readonly seed?: WorkbenchDataSeed;
  readonly editorSearch?: string;
}

interface WorkbenchSessionState extends WorkbenchSessionPayload {
  readonly instanceId: string;
  readonly editorSearch: string;
}

interface WorkbenchWindowContextValue {
  readonly session: WorkbenchSessionState | null;
  readonly windowState: WorkbenchWindowState;
  openSession: (payload: WorkbenchSessionPayload) => void;
  closeSession: () => void;
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  restoreWindow: () => void;
  shouldBypassUnsavedGuard: () => boolean;
}

const WorkbenchWindowContext = createContext<WorkbenchWindowContextValue | null>(null);

export function useWorkbenchWindow() {
  const context = useContext(WorkbenchWindowContext);
  if (!context) {
    throw new Error("useWorkbenchWindow must be used within a WorkbenchWindowProvider");
  }
  return context;
}

interface WorkbenchWindowProviderProps {
  readonly workspaceId: string;
  readonly children: ReactNode;
}

export function WorkbenchWindowProvider({ workspaceId, children }: WorkbenchWindowProviderProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState<WorkbenchSessionState | null>(null);
  const [windowState, setWindowState] = useState<WorkbenchWindowState>("restored");
  const instanceCounter = useRef(0);
  const navigationIntent = useRef<"dock" | "close" | null>(null);
  const guardBypassRef = useRef(false);

  const returnPathStorage = useMemo(
    () => createScopedStorage(getWorkbenchReturnPathStorageKey(workspaceId)),
    [workspaceId],
  );
  const defaultReturnPath = useMemo(() => `/workspaces/${workspaceId}/config-builder`, [workspaceId]);

  const editorRouteConfigId = useMemo(
    () => extractEditorRouteConfigId(location.pathname, workspaceId),
    [location.pathname, workspaceId],
  );
  const onEditorRoute = Boolean(editorRouteConfigId);

  useEffect(() => {
    if (!returnPathStorage.get<string>()) {
      returnPathStorage.set(defaultReturnPath);
    }
  }, [returnPathStorage, defaultReturnPath]);

  useEffect(() => {
    if (!onEditorRoute) {
      returnPathStorage.set(`${location.pathname}${location.search}${location.hash}`);
    }
  }, [onEditorRoute, location.pathname, location.search, location.hash, returnPathStorage]);

  useEffect(() => {
    if (!session) {
      navigationIntent.current = null;
      return;
    }

    const intent = navigationIntent.current;

    if (onEditorRoute && editorRouteConfigId === session.configId) {
      if (intent === "dock") {
        navigationIntent.current = null;
        setWindowState("minimized");
        return;
      }
      if (intent) {
        navigationIntent.current = null;
      }
      return;
    }

    if (intent === "dock") {
      navigationIntent.current = null;
      return;
    }

    if (intent === "close") {
      navigationIntent.current = null;
      return;
    }

    setSession(null);
    setWindowState("restored");
    navigationIntent.current = null;
  }, [session, onEditorRoute, editorRouteConfigId, windowState]);

  useEffect(() => {
    if (!session) {
      return;
    }
    if (!onEditorRoute || editorRouteConfigId !== session.configId) {
      return;
    }
    const normalizedSearch = normalizeSearchString(location.search);
    if (normalizedSearch === session.editorSearch) {
      return;
    }
    setSession((current) => {
      if (!current || current.instanceId !== session.instanceId) {
        return current;
      }
      return { ...current, editorSearch: normalizedSearch };
    });
  }, [session, onEditorRoute, editorRouteConfigId, location.search]);

  const ensureReturnPath = useCallback(() => {
    return returnPathStorage.get<string>() ?? defaultReturnPath;
  }, [returnPathStorage, defaultReturnPath]);

  const setOverrideSearchParams = useCallback(
    (init: SetSearchParamsInit) => {
      setSession((current) => {
        if (!current) {
          return current;
        }
        const base = new URLSearchParams(current.editorSearch);
        const nextInit = typeof init === "function" ? init(new URLSearchParams(base)) : init;
        const nextParams = toURLSearchParams(nextInit);
        const nextSearch = nextParams.toString();
        if (nextSearch === current.editorSearch) {
          return current;
        }
        return { ...current, editorSearch: nextSearch };
      });
    },
    [],
  );

  const openSession = useCallback(
    (payload: WorkbenchSessionPayload) => {
      const normalizedSearch = normalizeSearchString(payload.editorSearch ?? location.search);
      let shouldRestoreWindow = windowState === "minimized";
      setSession((current) => {
        if (current && current.workspaceId === payload.workspaceId && current.configId === payload.configId) {
          const nextSeed = payload.seed ?? current.seed;
          const nextEditorSearch =
            payload.editorSearch !== undefined ? normalizedSearch : current.editorSearch;
          if (
            current.configName === payload.configName &&
            current.configDisplayName === payload.configDisplayName &&
            current.seed === nextSeed &&
            current.editorSearch === nextEditorSearch
          ) {
            return current;
          }
          return {
            ...current,
            configName: payload.configName,
            configDisplayName: payload.configDisplayName,
            seed: nextSeed,
            editorSearch: nextEditorSearch,
          };
        }
        shouldRestoreWindow = true;
        instanceCounter.current += 1;
        return {
          ...payload,
          editorSearch: normalizedSearch,
          instanceId: `${payload.workspaceId}:${payload.configId}:${instanceCounter.current}`,
        };
      });
      if (shouldRestoreWindow) {
        setWindowState("restored");
      }
    },
    [location.search, windowState],
  );

  const closeSession = useCallback(() => {
    if (!session) {
      return;
    }
    setSession(null);
    setWindowState("restored");
    navigationIntent.current = "close";
    navigate(ensureReturnPath());
  }, [session, navigate, ensureReturnPath]);

  const minimizeWindow = useCallback(() => {
    if (!session) {
      return;
    }
    guardBypassRef.current = true;
    setWindowState("minimized");
    navigationIntent.current = "dock";
    navigate(ensureReturnPath());
  }, [session, navigate, ensureReturnPath]);

  const restoreWindow = useCallback(() => {
    if (!session) {
      return;
    }
    setWindowState("restored");
    const target = buildEditorTarget(session.workspaceId, session.configId, session.editorSearch);
    if (`${location.pathname}${location.search}` !== target) {
      navigate(target);
    }
  }, [session, navigate, location.pathname, location.search]);

  const maximizeWindow = useCallback(() => {
    if (!session) {
      return;
    }
    setWindowState("maximized");
  }, [session]);

  const consumeGuardBypass = useCallback(() => {
    const bypass = guardBypassRef.current;
    guardBypassRef.current = false;
    return bypass;
  }, []);

  const contextValue = useMemo<WorkbenchWindowContextValue>(
    () => ({
      session,
      windowState,
      openSession,
      closeSession,
      minimizeWindow,
      maximizeWindow,
      restoreWindow,
      shouldBypassUnsavedGuard: consumeGuardBypass,
    }),
    [
      session,
      windowState,
      openSession,
      closeSession,
      minimizeWindow,
      maximizeWindow,
      restoreWindow,
      consumeGuardBypass,
    ],
  );

  const shouldOverrideSearch =
    Boolean(session) && (!onEditorRoute || editorRouteConfigId !== session?.configId);
  const searchParamsOverride = useMemo(
    () =>
      shouldOverrideSearch && session
        ? {
            params: new URLSearchParams(session.editorSearch),
            setSearchParams: setOverrideSearchParams,
          }
        : null,
    [shouldOverrideSearch, session, setOverrideSearchParams],
  );

  return (
    <WorkbenchWindowContext.Provider value={contextValue}>
      {children}
      <SearchParamsOverrideProvider value={searchParamsOverride}>
        <WorkbenchWindowLayer
          session={session}
          windowState={windowState}
          onClose={closeSession}
          onMinimize={minimizeWindow}
          onMaximize={maximizeWindow}
          onRestore={restoreWindow}
          shouldBypassUnsavedGuard={consumeGuardBypass}
        />
      </SearchParamsOverrideProvider>
      {session && windowState === "minimized" ? (
        <WorkbenchDock
          configName={session.configName}
          onRestore={restoreWindow}
          onDismiss={closeSession}
        />
      ) : null}
    </WorkbenchWindowContext.Provider>
  );
}

function WorkbenchWindowLayer({
  session,
  windowState,
  onClose,
  onMinimize,
  onMaximize,
  onRestore,
  shouldBypassUnsavedGuard,
}: {
  readonly session: WorkbenchSessionState | null;
  readonly windowState: WorkbenchWindowState;
  readonly onClose: () => void;
  readonly onMinimize: () => void;
  readonly onMaximize: () => void;
  readonly onRestore: () => void;
  readonly shouldBypassUnsavedGuard: () => boolean;
}) {
  if (!session || windowState !== "maximized") {
    return null;
  }
  return (
    <div className="fixed inset-0 z-40 flex flex-col bg-background">
      <Workbench
        key={session.instanceId}
        workspaceId={session.workspaceId}
        configId={session.configId}
        configName={session.configName}
        configDisplayName={session.configDisplayName}
        seed={session.seed}
        windowState="maximized"
        onCloseWorkbench={onClose}
        onMinimizeWindow={onMinimize}
        onMaximizeWindow={onMaximize}
        onRestoreWindow={onRestore}
        shouldBypassUnsavedGuard={shouldBypassUnsavedGuard}
      />
    </div>
  );
}

interface WorkbenchDockProps {
  readonly configName: string;
  readonly onRestore: () => void;
  readonly onDismiss: () => void;
}

function WorkbenchDock({ configName, onRestore, onDismiss }: WorkbenchDockProps) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40">
      <div className="pointer-events-auto border-t border-border bg-card/95 shadow-top backdrop-blur">
        <div className="relative mx-auto flex h-14 max-w-6xl items-center px-4 text-foreground">
          <button
            type="button"
            onClick={onRestore}
            className="group flex min-w-0 flex-1 items-center gap-4 rounded-md px-3 py-1.5 text-left transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-foreground shadow-inner">
              <DockWindowIcon className="h-4 w-4" />
            </span>
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="text-[10px] font-semibold uppercase tracking-[0.32em] text-muted-foreground">
                Config workbench
              </span>
              <span className="truncate text-sm font-semibold text-foreground" title={configName}>
                {configName}
              </span>
            </span>
            <span className="ml-auto inline-flex items-center rounded border border-border bg-card px-2 py-0.5 text-[11px] font-medium text-muted-foreground transition group-hover:bg-muted">
              Restore
            </span>
          </button>
          <div className="ml-3 flex h-10 overflow-hidden rounded-md border border-border bg-card text-muted-foreground">
            <DockActionButton ariaLabel="Restore minimized workbench" onClick={onRestore} destructive={false}>
              <DockRestoreIcon className="h-3.5 w-3.5" />
            </DockActionButton>
            <DockActionButton ariaLabel="Close minimized workbench" onClick={onDismiss} destructive>
              <DockCloseIcon className="h-3.5 w-3.5" />
            </DockActionButton>
          </div>
        </div>
      </div>
    </div>
  );
}

function DockActionButton({
  ariaLabel,
  onClick,
  children,
  destructive = false,
}: {
  readonly ariaLabel: string;
  readonly onClick: () => void;
  readonly children: ReactNode;
  readonly destructive?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={clsx(
        "flex h-full w-12 items-center justify-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
        destructive ? "text-destructive hover:bg-destructive/10" : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function extractEditorRouteConfigId(pathname: string, workspaceId: string) {
  const base = `/workspaces/${workspaceId}/config-builder/`;
  if (!pathname.startsWith(base)) {
    return null;
  }
  const segments = pathname.slice(base.length).split("/").filter(Boolean);
  if (segments.length >= 2 && segments[1] === "editor") {
    try {
      return decodeURIComponent(segments[0]);
    } catch {
      return segments[0];
    }
  }
  return null;
}

function buildEditorTarget(workspaceId: string, configId: string, search: string) {
  const base = `/workspaces/${workspaceId}/config-builder/${encodeURIComponent(configId)}/editor`;
  return search.length > 0 ? `${base}?${search}` : base;
}

function normalizeSearchString(search: string | null | undefined) {
  if (!search) {
    return "";
  }
  return search.startsWith("?") ? search.slice(1) : search;
}

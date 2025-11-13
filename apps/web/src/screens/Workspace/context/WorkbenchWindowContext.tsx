import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";

import { Workbench } from "@screens/Workspace/sections/ConfigBuilder/workbench/Workbench";
import type { WorkbenchDataSeed } from "@screens/Workspace/sections/ConfigBuilder/workbench/types";
import { getWorkbenchReturnPathStorageKey } from "@screens/Workspace/sections/ConfigBuilder/workbench/state/workbenchWindowState";

import { createScopedStorage } from "@shared/storage";
import {
  SearchParamsOverrideProvider,
  toURLSearchParams,
  type SetSearchParamsInit,
  type SetSearchParamsOptions,
} from "@app/nav/urlState";

type WorkbenchWindowMode = "maximized" | "minimized";

interface WorkbenchSessionPayload {
  readonly workspaceId: string;
  readonly configId: string;
  readonly configName: string;
  readonly seed?: WorkbenchDataSeed;
  readonly editorSearch?: string;
}

interface WorkbenchSessionState extends WorkbenchSessionPayload {
  readonly instanceId: string;
  readonly editorSearch: string;
}

interface WorkbenchWindowContextValue {
  readonly session: WorkbenchSessionState | null;
  readonly mode: WorkbenchWindowMode;
  openSession: (payload: WorkbenchSessionPayload) => void;
  closeSession: () => void;
  minimizeSession: () => void;
  restoreSession: () => void;
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
  const [mode, setMode] = useState<WorkbenchWindowMode>("maximized");
  const instanceCounter = useRef(0);
  const navigationIntent = useRef<"minimize" | "close" | null>(null);
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
      if (intent !== "minimize") {
        setMode("maximized");
      }
      if (intent !== "minimize") {
        navigationIntent.current = null;
      }
      return;
    }

    if (!onEditorRoute) {
      if (intent === "minimize") {
        navigationIntent.current = null;
        return;
      }
      if (mode === "maximized" && intent === null) {
        setSession(null);
        return;
      }
      navigationIntent.current = null;
    }
  }, [session, onEditorRoute, editorRouteConfigId, mode]);

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
    (init: SetSearchParamsInit, _options?: SetSearchParamsOptions) => {
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
      setSession((current) => {
        if (current && current.workspaceId === payload.workspaceId && current.configId === payload.configId) {
          return {
            ...current,
            configName: payload.configName,
            seed: payload.seed ?? current.seed,
            editorSearch:
              payload.editorSearch !== undefined ? normalizedSearch : current.editorSearch,
          };
        }
        instanceCounter.current += 1;
        return {
          ...payload,
          editorSearch: normalizedSearch,
          instanceId: `${payload.workspaceId}:${payload.configId}:${instanceCounter.current}`,
        };
      });
      setMode("maximized");
    },
    [location.search],
  );

  const closeSession = useCallback(() => {
    if (!session) {
      return;
    }
    setSession(null);
    setMode("maximized");
    navigationIntent.current = "close";
    navigate(ensureReturnPath());
  }, [session, navigate, ensureReturnPath]);

  const minimizeSession = useCallback(() => {
    if (!session) {
      return;
    }
    guardBypassRef.current = true;
    setMode("minimized");
    navigationIntent.current = "minimize";
    navigate(ensureReturnPath());
  }, [session, navigate, ensureReturnPath]);

  const restoreSession = useCallback(() => {
    if (!session) {
      return;
    }
    setMode("maximized");
    const target = buildEditorTarget(session.workspaceId, session.configId, session.editorSearch);
    if (`${location.pathname}${location.search}` !== target) {
      navigate(target);
    }
  }, [session, navigate, location.pathname, location.search]);

  const contextValue = useMemo<WorkbenchWindowContextValue>(
    () => ({
      session,
      mode,
      openSession,
      closeSession,
      minimizeSession,
      restoreSession,
    }),
    [session, mode, openSession, closeSession, minimizeSession, restoreSession],
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

  const consumeGuardBypass = useCallback(() => {
    const bypass = guardBypassRef.current;
    guardBypassRef.current = false;
    return bypass;
  }, []);

  return (
    <WorkbenchWindowContext.Provider value={contextValue}>
      {children}
      <SearchParamsOverrideProvider value={searchParamsOverride}>
        <WorkbenchWindowLayer
          session={session}
          mode={mode}
          onClose={closeSession}
          onMinimize={minimizeSession}
          shouldBypassUnsavedGuard={consumeGuardBypass}
        />
      </SearchParamsOverrideProvider>
      {session && mode === "minimized" ? (
        <WorkbenchDock
          configName={session.configName}
          onRestore={restoreSession}
          onDismiss={closeSession}
        />
      ) : null}
    </WorkbenchWindowContext.Provider>
  );
}

function WorkbenchWindowLayer({
  session,
  mode,
  onClose,
  onMinimize,
  shouldBypassUnsavedGuard,
}: {
  readonly session: WorkbenchSessionState | null;
  readonly mode: WorkbenchWindowMode;
  readonly onClose: () => void;
  readonly onMinimize: () => void;
  readonly shouldBypassUnsavedGuard: () => boolean;
}) {
  if (!session) {
    return null;
  }
  const hidden = mode === "minimized";
  return (
    <div
      className={clsx(
        "fixed inset-0 z-40 flex flex-col bg-slate-50 transition-[opacity,transform] duration-200 ease-out",
        hidden ? "pointer-events-none opacity-0 translate-y-4" : "pointer-events-auto opacity-100 translate-y-0",
      )}
      aria-hidden={hidden}
    >
      <Workbench
        key={session.instanceId}
        workspaceId={session.workspaceId}
        configId={session.configId}
        configName={session.configName}
        seed={session.seed}
        onCloseWorkbench={onClose}
        onMinimizeWorkbench={onMinimize}
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
      <div className="pointer-events-auto border-t border-slate-200 bg-white/95 shadow-[0_-12px_40px_rgba(15,23,42,0.15)] backdrop-blur">
        <div className="relative mx-auto flex h-14 max-w-6xl items-center px-4 text-slate-900">
          <button
            type="button"
            onClick={onRestore}
            className="group flex min-w-0 flex-1 items-center gap-4 rounded-md px-3 py-1.5 text-left transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/40"
          >
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-brand-600 shadow-inner">
              <DockWindowIcon />
            </span>
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="text-[10px] font-semibold uppercase tracking-[0.32em] text-slate-400">
                Config workbench
              </span>
              <span className="truncate text-sm font-semibold text-slate-900" title={configName}>
                {configName}
              </span>
            </span>
            <span className="ml-auto inline-flex items-center rounded border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600 transition group-hover:border-slate-300 group-hover:bg-slate-50">
              Restore
            </span>
          </button>
          <div className="ml-3 flex h-10 overflow-hidden rounded-md border border-slate-200 bg-white text-slate-500">
            <DockActionButton ariaLabel="Restore minimized workbench" onClick={onRestore} destructive={false}>
              <DockRestoreIcon />
            </DockActionButton>
            <DockActionButton ariaLabel="Close minimized workbench" onClick={onDismiss} destructive>
              <DockCloseIcon />
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
  readonly children: JSX.Element;
  readonly destructive?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={ariaLabel}
      onClick={onClick}
      className={clsx(
        "flex h-full w-12 items-center justify-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/40",
        destructive ? "text-rose-600 hover:bg-rose-50" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
      )}
    >
      {children}
    </button>
  );
}

function DockWindowIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="2" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
      <rect x="9" y="2" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
      <rect x="2" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
      <rect x="9" y="9" width="5" height="5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function DockRestoreIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 5.5h6v6h-6z" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function DockCloseIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M4.5 11.5 11.5 4.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M11.5 11.5 4.5 4.5" stroke="currentColor" strokeWidth="1.2" />
    </svg>
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

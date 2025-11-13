import { useEffect, useMemo, useState } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { useQueryClient } from "@tanstack/react-query";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS, type WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";
import { WorkspaceProvider } from "@screens/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider } from "@screens/Workspace/context/WorkbenchWindowContext";
import { createScopedStorage } from "@shared/storage";
import { writePreferredWorkspace } from "@screens/Workspace/state/workspace-preferences";
import { GlobalTopBar } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { WorkspaceNav } from "@screens/Workspace/components/WorkspaceNav";
import { defaultWorkspaceSection } from "@screens/Workspace/components/workspace-navigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import { Alert } from "@ui/Alert";
import { PageState } from "@ui/PageState";

import WorkspaceOverviewRoute from "@screens/Workspace/sections/Overview";
import WorkspaceDocumentsRoute from "@screens/Workspace/sections/Documents";
import DocumentDetailRoute from "@screens/Workspace/sections/Documents/components/DocumentDetail";
import WorkspaceJobsRoute from "@screens/Workspace/sections/Jobs";
import WorkspaceConfigsIndexRoute from "@screens/Workspace/sections/ConfigBuilder";
import WorkspaceConfigRoute from "@screens/Workspace/sections/ConfigBuilder/detail";
import ConfigEditorWorkbenchRoute from "@screens/Workspace/sections/ConfigBuilder/workbench";
import WorkspaceSettingsRoute from "@screens/Workspace/sections/Settings";

type WorkspaceSectionRender =
  | { readonly kind: "redirect"; readonly to: string }
  | { readonly kind: "content"; readonly key: string; readonly element: JSX.Element; readonly fullHeight?: boolean };

export default function WorkspaceScreen() {
  return (
    <RequireSession>
      <WorkspaceContent />
    </RequireSession>
  );
}

function WorkspaceContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = workspacesQuery.data?.items ?? [];
  const identifier = extractWorkspaceIdentifier(location.pathname);
  const workspace = useMemo(() => findWorkspace(workspaces, identifier), [workspaces, identifier]);

  useEffect(() => {
    if (workspacesQuery.data) {
      queryClient.setQueryData(
        workspacesKeys.list(WORKSPACE_LIST_DEFAULT_PARAMS),
        workspacesQuery.data,
      );
    }
  }, [queryClient, workspacesQuery.data]);

  useEffect(() => {
    if (!workspacesQuery.isLoading && !workspacesQuery.isError && workspaces.length === 0) {
      navigate("/workspaces", { replace: true });
    }
  }, [workspacesQuery.isLoading, workspacesQuery.isError, workspaces.length, navigate]);

  useEffect(() => {
    if (workspace && !identifier) {
      navigate(`/workspaces/${workspace.id}/${defaultWorkspaceSection.path}${location.search}${location.hash}`, {
        replace: true,
      });
    }
  }, [workspace, identifier, location.search, location.hash, navigate]);

  useEffect(() => {
    if (!workspace || !identifier) {
      return;
    }

    if (identifier !== workspace.id) {
      const canonical = buildCanonicalPath(location.pathname, location.search, workspace.id, identifier);
      if (canonical !== location.pathname + location.search) {
        navigate(canonical + location.hash, { replace: true });
      }
    }
  }, [workspace, identifier, location.pathname, location.search, location.hash, navigate]);

  useEffect(() => {
    if (workspace) {
      writePreferredWorkspace(workspace);
    }
  }, [workspace]);

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Loading workspace" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-6 text-center">
        <PageState
          title="Unable to load workspace"
          description="We were unable to fetch workspace information. Refresh the page to try again."
          variant="error"
        />
        <button
          type="button"
          className="focus-ring rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100"
          onClick={() => workspacesQuery.refetch()}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!workspace) {
    return null;
  }

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceShell workspace={workspace} />
    </WorkspaceProvider>
  );
}

interface WorkspaceShellProps {
  readonly workspace: WorkspaceProfile;
}

function WorkspaceShell({ workspace }: WorkspaceShellProps) {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;

  const navStorage = useMemo(
    () => createScopedStorage(`ade.ui.workspace.${workspace.id}.navCollapsed`),
    [workspace.id],
  );
  const [isNavCollapsed, setIsNavCollapsed] = useState(() => {
    const stored = navStorage.get<boolean>();
    return typeof stored === "boolean" ? stored : false;
  });

  useEffect(() => {
    const stored = navStorage.get<boolean>();
    setIsNavCollapsed(typeof stored === "boolean" ? stored : false);
  }, [navStorage]);

  useEffect(() => {
    navStorage.set(isNavCollapsed);
  }, [isNavCollapsed, navStorage]);

  const topBarLeading = (
    <button
      type="button"
      className="focus-ring inline-flex items-center gap-3 rounded-xl border border-transparent bg-white px-3 py-2 text-left text-sm font-semibold text-slate-900 shadow-sm transition hover:border-slate-200"
      onClick={() => navigate("/workspaces")}
    >
      <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm">
        ADE
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-sm font-semibold text-slate-900">{workspace.name}</span>
        <span className="text-xs text-slate-400">Workspace</span>
      </span>
    </button>
  );

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarTrailing = (
    <div className="flex items-center gap-2">
      <ProfileDropdown displayName={displayName} email={email} />
    </div>
  );

  const primaryNav = (
    <WorkspaceNav
      workspace={workspace}
      collapsed={isNavCollapsed}
      onToggleCollapse={() => setIsNavCollapsed((current) => !current)}
    />
  );

  const segments = extractSectionSegments(location.pathname, workspace.id);
  const section = resolveWorkspaceSection(workspace.id, segments, location.search, location.hash);

  useEffect(() => {
    if (section?.kind === "redirect") {
      navigate(section.to, { replace: true });
    }
  }, [section, navigate]);

  if (!section || section.kind === "redirect") {
    return null;
  }

  const fullHeightLayout = section.fullHeight ?? false;

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <GlobalTopBar leading={topBarLeading} trailing={topBarTrailing} />
      <div className="relative flex flex-1 overflow-hidden" key={`section-${section.key}`}>
        {primaryNav}
        <main
          className={clsx(
            "relative flex-1",
            fullHeightLayout ? "flex min-h-0 flex-col overflow-hidden" : "overflow-y-auto",
          )}
        >
          <div
            className={clsx(
              fullHeightLayout
                ? "flex w-full flex-1 min-h-0 flex-col px-0 py-0"
                : "mx-auto flex w-full max-w-7xl flex-col px-4 py-6",
            )}
          >
            {safeModeEnabled ? (
              <div className={clsx("mb-4", fullHeightLayout ? "px-6 pt-4" : "")}>
                <Alert tone="warning" heading="Safe mode active">
                  {safeModeDetail}
                </Alert>
              </div>
            ) : null}
            <div
              className={
                fullHeightLayout
                  ? "flex flex-1 min-h-0 flex-col"
                  : "rounded-2xl border border-slate-200 bg-white p-6 shadow-soft"
              }
            >
              {section.element}
            </div>
          </div>
        </main>
        {minimizedWorkbench ? (
          <WorkbenchDock
            configName={minimizedWorkbench.configName}
            onRestore={handleRestoreWorkbench}
            onDismiss={handleDismissWorkbenchDock}
          />
        ) : null}
      </div>
    </div>
  );
}

function extractWorkspaceIdentifier(pathname: string) {
  const match = pathname.match(/^\/workspaces\/([^/]+)/);
  return match?.[1] ?? null;
}

function extractSectionSegments(pathname: string, workspaceId: string) {
  const base = `/workspaces/${workspaceId}`;
  if (!pathname.startsWith(base)) {
    return [];
  }
  const remainder = pathname.slice(base.length);
  return remainder
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0);
}

function findWorkspace(workspaces: WorkspaceProfile[], identifier: string | null) {
  if (!identifier) {
    return workspaces[0] ?? null;
  }
  return (
    workspaces.find((workspace) => workspace.id === identifier) ??
    workspaces.find((workspace) => workspace.slug === identifier) ??
    workspaces[0] ??
    null
  );
}

function buildCanonicalPath(pathname: string, search: string, resolvedId: string, currentId: string) {
  const base = `/workspaces/${currentId}`;
  const trailing = pathname.startsWith(base) ? pathname.slice(base.length) : "";
  const normalized = trailing && trailing !== "/" ? trailing : `/${defaultWorkspaceSection.path}`;
  return `/workspaces/${resolvedId}${normalized}${search}`;
}

export function resolveWorkspaceSection(
  workspaceId: string,
  segments: string[],
  search: string,
  hash: string,
): WorkspaceSectionRender | null {
  const suffix = `${search}${hash}`;

  if (segments.length === 0) {
    return {
      kind: "redirect",
      to: `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}${suffix}`,
    };
  }

  const [first, second, third] = segments;
  switch (first) {
    case "overview":
      return { kind: "content", key: "overview", element: <WorkspaceOverviewRoute /> };
    case defaultWorkspaceSection.path:
    case "documents": {
      if (!second) {
        return { kind: "content", key: "documents", element: <WorkspaceDocumentsRoute /> };
      }
      return {
        kind: "content",
        key: `documents:${second}`,
        element: <DocumentDetailRoute params={{ documentId: decodeURIComponent(second) }} />,
      };
    }
    case "jobs":
      return { kind: "content", key: "jobs", element: <WorkspaceJobsRoute /> };
    case "config-builder": {
      if (!second) {
        return { kind: "content", key: "config-builder", element: <WorkspaceConfigsIndexRoute /> };
      }
      if (third === "editor") {
        return {
          kind: "content",
          key: `config-builder:${second}:editor`,
          element: <ConfigEditorWorkbenchRouteWithParams configId={decodeURIComponent(second)} />,
          fullHeight: true,
        };
      }
      return {
        kind: "content",
        key: `config-builder:${second}`,
        element: <WorkspaceConfigRoute params={{ configId: decodeURIComponent(second) }} />,
      };
    }
    case "configs": {
      const legacyTarget = `/workspaces/${workspaceId}/config-builder${second ? `/${second}` : ""}${third ? `/${third}` : ""}`;
      return {
        kind: "redirect",
        to: `${legacyTarget}${suffix}`,
      };
    }
    case "settings":
      return { kind: "content", key: "settings", element: <WorkspaceSettingsRoute /> };
    default:
      return {
        kind: "content",
        key: `not-found:${segments.join("/")}`,
        element: (
          <PageState
            title="Section not found"
            description="The requested workspace section could not be located."
            variant="error"
          />
        ),
      };
  }
}
function ConfigEditorWorkbenchRouteWithParams({ configId }: { readonly configId: string }) {
  return <ConfigEditorWorkbenchRoute params={{ configId }} />;
}

export function getDefaultWorkspacePath(workspaceId: string) {
  return `/workspaces/${workspaceId}/${defaultWorkspaceSection.path}`;
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
        destructive
          ? "text-rose-600 hover:bg-rose-50"
          : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
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
      <path d="M6 4h6v6" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function DockCloseIcon() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M5 5l6 6M11 5l-6 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

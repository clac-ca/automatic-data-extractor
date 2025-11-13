import { useCallback, useEffect, useMemo, useState } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "@app/nav/history";
import { useQueryClient } from "@tanstack/react-query";

import { RequireSession } from "@shared/auth/components/RequireSession";
import { useSession } from "@shared/auth/context/SessionContext";
import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS, type WorkspaceProfile } from "@screens/Workspace/api/workspaces-api";
import { WorkspaceProvider } from "@screens/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider, useWorkbenchWindow } from "@screens/Workspace/context/WorkbenchWindowContext";
import { createScopedStorage } from "@shared/storage";
import { writePreferredWorkspace } from "@screens/Workspace/state/workspace-preferences";
import { GlobalTopBar } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { WorkspaceNav, WorkspaceNavList } from "@screens/Workspace/components/WorkspaceNav";
import { defaultWorkspaceSection, getWorkspacePrimaryNavigation } from "@screens/Workspace/components/workspace-navigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@shared/system";
import { Alert } from "@ui/Alert";
import { PageState } from "@ui/PageState";
import { useShortcutHint } from "@shared/hooks/useShortcutHint";
import type { GlobalSearchSuggestion } from "@app/shell/GlobalTopBar";

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
  return (
    <WorkbenchWindowProvider workspaceId={workspace.id}>
      <WorkspaceShellLayout workspace={workspace} />
    </WorkbenchWindowProvider>
  );
}

function WorkspaceShellLayout({ workspace }: WorkspaceShellProps) {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const { session: workbenchSession, focusMode } = useWorkbenchWindow();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const shortcutHint = useShortcutHint();
  const workspaceNavItems = useMemo(
    () => getWorkspacePrimaryNavigation(workspace),
    [workspace],
  );
  const [workspaceSearchQuery, setWorkspaceSearchQuery] = useState("");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const workspaceSearchNormalized = workspaceSearchQuery.trim().toLowerCase();
  const immersiveWorkbenchActive = Boolean(workbenchSession && focusMode === "immersive");
  const workspaceSearchSuggestions = useMemo(
    () =>
      workspaceNavItems.map((item) => ({
        id: item.id,
        label: item.label,
        description: `Jump to ${item.label}`,
        icon: <item.icon className="h-4 w-4 text-slate-400" aria-hidden />,
      })),
    [workspaceNavItems],
  );

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

  useEffect(() => {
    setWorkspaceSearchQuery("");
  }, [workspace.id]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setIsMobileNavOpen(false);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }
    const originalOverflow = document.body.style.overflow;
    if (isMobileNavOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = originalOverflow || "";
    }
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isMobileNavOpen]);

  useEffect(() => {
    if (immersiveWorkbenchActive) {
      setIsMobileNavOpen(false);
    }
  }, [immersiveWorkbenchActive]);

  const handleWorkspaceSearchSubmit = useCallback(() => {
    if (!workspaceSearchNormalized) {
      return;
    }
    const match =
      workspaceNavItems.find((item) => item.label.toLowerCase().includes(workspaceSearchNormalized)) ??
      workspaceNavItems.find((item) => item.id.toLowerCase().includes(workspaceSearchNormalized));
    if (match) {
      navigate(match.href);
    }
  }, [workspaceSearchNormalized, workspaceNavItems, navigate]);
  const handleWorkspaceSuggestionSelect = useCallback(
    (suggestion: GlobalSearchSuggestion) => {
      const match = workspaceNavItems.find((item) => item.id === suggestion.id);
      if (match) {
        navigate(match.href);
        setWorkspaceSearchQuery("");
      }
    },
    [workspaceNavItems, navigate],
  );

  const openMobileNav = useCallback(() => setIsMobileNavOpen(true), []);
  const closeMobileNav = useCallback(() => setIsMobileNavOpen(false), []);

  const topBarBrand = (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={openMobileNav}
        className="focus-ring inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-600 shadow-sm lg:hidden"
        aria-label="Open workspace navigation"
      >
        <MenuIcon />
      </button>
    </div>
  );

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarTrailing = (
    <div className="flex items-center gap-2">
      <ProfileDropdown displayName={displayName} email={email} />
    </div>
  );
  const workspaceSearch = {
    value: workspaceSearchQuery,
    onChange: setWorkspaceSearchQuery,
    onSubmit: handleWorkspaceSearchSubmit,
    placeholder: `Search ${workspace.name} or jump to a section`,
    shortcutHint,
    scopeLabel: workspace.name,
    suggestions: workspaceSearchSuggestions,
    onSelectSuggestion: handleWorkspaceSuggestionSelect,
  };

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
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      {!immersiveWorkbenchActive ? (
        <WorkspaceNav
          workspace={workspace}
          items={workspaceNavItems}
          collapsed={isNavCollapsed}
          onToggleCollapse={() => setIsNavCollapsed((current) => !current)}
          onGoToWorkspaces={() => navigate("/workspaces")}
        />
      ) : null}
      <div className="flex flex-1 flex-col">
        {!immersiveWorkbenchActive ? (
          <GlobalTopBar brand={topBarBrand} trailing={topBarTrailing} search={workspaceSearch} />
        ) : null}
        {!immersiveWorkbenchActive && isMobileNavOpen ? (
          <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
            <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={closeMobileNav} />
            <div className="absolute inset-y-0 left-0 flex h-full w-[min(20rem,85vw)] max-w-xs flex-col rounded-r-3xl border-r border-slate-100/70 bg-gradient-to-b from-white via-slate-50 to-white/95 shadow-[0_45px_90px_-50px_rgba(15,23,42,0.85)]">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                <div className="flex flex-col leading-tight">
                  <span className="text-sm font-semibold text-slate-900">{workspace.name}</span>
                  <span className="text-xs text-slate-400">Workspace navigation</span>
                </div>
                <button
                  type="button"
                  onClick={closeMobileNav}
                  className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500"
                  aria-label="Close navigation"
                >
                  <CloseIcon />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-3 py-4">
                <WorkspaceNavList items={workspaceNavItems} onNavigate={closeMobileNav} showHeading={false} />
              </div>
            </div>
          </div>
        ) : null}
        <div className="relative flex flex-1 min-w-0 overflow-hidden" key={`section-${section.key}`}>
          <main
            className={clsx(
              "relative flex-1 min-w-0",
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
        </div>
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

function MenuIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M4 6h12" strokeLinecap="round" />
      <path d="M4 10h12" strokeLinecap="round" />
      <path d="M4 14h8" strokeLinecap="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M6 6l8 8" strokeLinecap="round" />
      <path d="M14 6l-8 8" strokeLinecap="round" />
    </svg>
  );
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

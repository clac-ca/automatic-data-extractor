import { useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactElement } from "react";

import clsx from "clsx";

import { useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { useSession } from "@components/providers/auth/SessionContext";
import { useWorkspacesQuery, workspacesKeys, WORKSPACE_LIST_DEFAULT_PARAMS } from "@hooks/workspaces";
import { writePreferredWorkspaceId } from "@lib/workspacePreferences";
import type { WorkspaceProfile } from "@schema/workspaces";
import { WorkspaceProvider } from "@pages/Workspace/context/WorkspaceContext";
import { WorkbenchWindowProvider, useWorkbenchWindow } from "@pages/Workspace/context/WorkbenchWindowContext";
import { createScopedStorage } from "@lib/storage";
import { uiStorageKeys } from "@lib/uiStorageKeys";
import { GlobalTopBar } from "@components/shell/GlobalTopBar";
import { GlobalNavSearch } from "@components/shell/GlobalNavSearch";
import { AppearanceMenu } from "@components/shell/AppearanceMenu";
import { ProfileDropdown } from "@components/shell/ProfileDropdown";
import { AboutVersionsModal } from "@components/shell/AboutVersionsModal";
import {
  WorkspaceNav,
  WorkspaceNavList,
  WORKSPACE_NAV_DRAWER_WIDTH,
  WORKSPACE_NAV_RAIL_WIDTH,
} from "@pages/Workspace/components/WorkspaceNav";
import { WorkspaceSwitcher } from "@pages/Workspace/components/WorkspaceSwitcher";
import { defaultWorkspaceSection, getWorkspacePrimaryNavigation } from "@pages/Workspace/components/workspaceNavigation";
import { DEFAULT_SAFE_MODE_MESSAGE, useSafeModeStatus } from "@hooks/system";
import { Alert } from "@/components/ui/alert";
import { PageState } from "@components/layouts/page-state";
import { CloseIcon, MenuIcon } from "@components/icons";

import DocumentsScreen from "@pages/Workspace/sections/Documents";
import RunsScreen from "@pages/Workspace/sections/Runs";
import ConfigBuilderScreen from "@pages/Workspace/sections/ConfigBuilder";
import ConfigurationDetailScreen from "@pages/Workspace/sections/ConfigBuilder/detail";
import ConfigBuilderWorkbenchScreen from "@pages/Workspace/sections/ConfigBuilder/workbench";
import WorkspaceSettingsScreen from "@pages/Workspace/sections/Settings";

type WorkspaceSectionRender =
  | { readonly kind: "redirect"; readonly to: string }
  | { readonly kind: "content"; readonly key: string; readonly element: ReactElement; readonly fullHeight?: boolean };

export default function WorkspaceScreen() {
  return <WorkspaceContent />;
}

function WorkspaceContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const workspacesQuery = useWorkspacesQuery();

  const workspaces = useMemo(
    () => workspacesQuery.data?.items ?? [],
    [workspacesQuery.data?.items],
  );
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
      writePreferredWorkspaceId(workspace.id);
    }
  }, [workspace]);


  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <PageState title="Loading workspace" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <PageState
          title="Unable to load workspace"
          description="We were unable to fetch workspace information. Refresh the page to try again."
          variant="error"
        />
        <button
          type="button"
          className="rounded-lg border border-border bg-card px-4 py-2 text-sm font-semibold text-muted-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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
  const { session: workbenchSession, windowState } = useWorkbenchWindow();
  const safeMode = useSafeModeStatus();
  const safeModeEnabled = safeMode.data?.enabled ?? false;
  const safeModeDetail = safeMode.data?.detail ?? DEFAULT_SAFE_MODE_MESSAGE;
  const [scrollContainer, setScrollContainer] = useState<HTMLElement | null>(null);
  const handleScrollContainerRef = useCallback((node: HTMLElement | null) => {
    setScrollContainer(node);
  }, []);
  const workspaceNavItems = useMemo(
    () => getWorkspacePrimaryNavigation(workspace),
    [workspace],
  );
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const immersiveWorkbenchActive = Boolean(workbenchSession && windowState === "maximized");

  const navPinnedStorage = useMemo(() => createScopedStorage(uiStorageKeys.sidebarPinned), []);
  const [isNavPinned, setIsNavPinned] = useState(() => {
    const pinned = navPinnedStorage.get<boolean>();
    return typeof pinned === "boolean" ? pinned : false;
  });

  useEffect(() => {
    navPinnedStorage.set(isNavPinned);
  }, [isNavPinned, navPinnedStorage]);

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


  const openMobileNav = useCallback(() => setIsMobileNavOpen(true), []);
  const closeMobileNav = useCallback(() => setIsMobileNavOpen(false), []);

  const topBarBrand = (
    <div className="flex min-w-0 items-center gap-3">
      <button
        type="button"
        onClick={openMobileNav}
        className={clsx(
          "inline-flex h-11 w-11 items-center justify-center rounded-xl border lg:hidden",
          "border-border/50 bg-background/60 text-muted-foreground transition",
          "hover:border-border/70 hover:bg-background/80 hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        )}
        aria-label="Open workspace navigation"
      >
        <MenuIcon className="h-4 w-4" />
      </button>
      <div className="hidden min-w-0 max-w-[14rem] flex-col leading-tight sm:flex lg:hidden">
        <span className="text-[0.63rem] font-semibold uppercase tracking-[0.35em] text-muted-foreground">
          Workspace
        </span>
        <span className="truncate text-sm font-semibold text-foreground">{workspace.name}</span>
      </div>
    </div>
  );

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarTrailing = (
    <div className="flex min-w-0 flex-nowrap items-center gap-2">
      <AppearanceMenu tone="header" />
      <ProfileDropdown
        displayName={displayName}
        email={email}
        tone="header"
        actions={[
          {
            id: "about-versions",
            label: "About / Versions",
            description: "ade-web, ade-api, ade-engine",
            onSelect: () => setIsVersionsModalOpen(true),
          },
        ]}
      />
    </div>
  );

  const segments = extractSectionSegments(location.pathname, workspace.id);
  const section = resolveWorkspaceSection(workspace.id, segments, location.search, location.hash);
  const topBarSearch = (
    <GlobalNavSearch
      scope={{
        kind: "workspace",
        workspaceId: workspace.id,
        workspaceName: workspace.name,
        navItems: workspaceNavItems,
      }}
    />
  );

  useEffect(() => {
    if (section?.kind === "redirect") {
      navigate(section.to, { replace: true });
    }
  }, [section, navigate]);

  if (!section || section.kind === "redirect") {
    return null;
  }

  const fullHeightLayout = section.fullHeight ?? false;

  const workspaceNavWidth = immersiveWorkbenchActive
    ? "0px"
    : isNavPinned
      ? WORKSPACE_NAV_DRAWER_WIDTH
      : WORKSPACE_NAV_RAIL_WIDTH;

  return (
    <>
      <AboutVersionsModal open={isVersionsModalOpen} onClose={() => setIsVersionsModalOpen(false)} />
      <div
        className={clsx(
          "grid min-w-0 h-screen grid-rows-[auto_1fr] grid-cols-1 bg-background text-foreground overflow-hidden",
          "lg:grid-cols-[var(--workspace-nav-width)_1fr]",
        )}
        style={
          {
            "--workspace-nav-width": workspaceNavWidth,
          } as CSSProperties
        }
      >
        {!immersiveWorkbenchActive ? (
          <div className="row-span-2 hidden min-h-0 min-w-0 lg:block">
            <WorkspaceNav
              workspace={workspace}
              items={workspaceNavItems}
              isPinned={isNavPinned}
              onTogglePinned={() => setIsNavPinned((current) => !current)}
              className="h-full"
            />
          </div>
        ) : null}
        <div className="relative row-span-2 col-start-1 flex min-h-0 min-w-0 flex-col lg:col-start-2">
          {!immersiveWorkbenchActive ? (
            <GlobalTopBar
              brand={topBarBrand}
              trailing={topBarTrailing}
              search={topBarSearch}
              scrollContainer={scrollContainer}
            />
          ) : null}
          <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden">
            {!immersiveWorkbenchActive && isMobileNavOpen ? (
              <div className="fixed inset-0 z-[var(--app-z-overlay)] lg:hidden" role="dialog" aria-modal="true">
                <button
                  type="button"
                  className="absolute inset-0 bg-overlay backdrop-blur-sm"
                  onClick={closeMobileNav}
                  aria-label="Close navigation"
                />
                <div className="absolute inset-y-0 left-0 flex h-full w-[min(20rem,85vw)] max-w-xs flex-col rounded-r-3xl border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-2xl">
                  <div className="flex items-center gap-3 border-b border-sidebar-border px-4 py-3">
                    <WorkspaceSwitcher
                      variant="drawer"
                      showLabel={false}
                      onNavigate={closeMobileNav}
                      className="min-w-0 flex-1"
                    />
                    <button
                      type="button"
                      onClick={closeMobileNav}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-sidebar-border bg-sidebar-accent text-sidebar-accent-foreground transition hover:bg-sidebar-accent/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar"
                      aria-label="Close navigation"
                    >
                      <CloseIcon className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto px-3 py-4">
                    <WorkspaceNavList items={workspaceNavItems} onNavigate={closeMobileNav} showHeading={false} />
                  </div>
                </div>
              </div>
            ) : null}
            <div className="relative flex min-h-0 min-w-0 flex-1 overflow-hidden" key={`section-${section.key}`}>
              <main
                id="main-content"
                tabIndex={-1}
                className={clsx(
                  "relative flex-1 min-h-0 min-w-0",
                  fullHeightLayout ? "flex flex-col overflow-hidden" : "overflow-y-auto",
                )}
                ref={handleScrollContainerRef}
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
                  <div className="flex min-h-0 min-w-0 flex-1 flex-col">
                    {section.element}
                  </div>
                </div>
              </main>
            </div>
          </div>
        </div>
      </div>
    </>
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
    case defaultWorkspaceSection.path:
    case "documents": {
      if (second) {
        const params = new URLSearchParams(search);
        params.set("doc", decodeURIComponent(second));
        const query = params.toString();
        return {
          kind: "redirect",
          to: `/workspaces/${workspaceId}/documents${query ? `?${query}` : ""}${hash}`,
        };
      }
      return { kind: "content", key: "documents", element: <DocumentsScreen />, fullHeight: true };
    }
    case "runs":
      return { kind: "content", key: "runs", element: <RunsScreen />, fullHeight: true };
    case "config-builder": {
      if (!second) {
        return { kind: "content", key: "config-builder", element: <ConfigBuilderScreen /> };
      }
      if (third === "editor") {
        return {
          kind: "content",
          key: `config-builder:${second}:editor`,
          element: <ConfigBuilderWorkbenchScreenWithParams configId={decodeURIComponent(second)} />,
          fullHeight: true,
        };
      }
      return {
        kind: "content",
        key: `config-builder:${second}`,
        element: <ConfigurationDetailScreen params={{ configId: decodeURIComponent(second) }} />,
      };
    }
    case "settings": {
      const remaining = segments.slice(1);
      const normalized = remaining.length > 0 ? remaining : [];
      const key = `settings:${normalized.length > 0 ? normalized.join(":") : "general"}`;
      return { kind: "content", key, element: <WorkspaceSettingsScreen sectionSegments={normalized} /> };
    }
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
function ConfigBuilderWorkbenchScreenWithParams({ configId }: { readonly configId: string }) {
  return <ConfigBuilderWorkbenchScreen params={{ configId }} />;
}

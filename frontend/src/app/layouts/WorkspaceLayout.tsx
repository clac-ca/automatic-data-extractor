import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Outlet, useLoaderData, useLocation, useMatches, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";

import { WorkspaceProvider, useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { workspaceKeys } from "../../features/workspaces/hooks/useWorkspacesQuery";
import type { WorkspaceLoaderData } from "../workspaces/loader";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import { buildWorkspaceSectionPath, defaultWorkspaceSection, matchWorkspaceSection } from "../workspaces/sections";
import { writePreferredWorkspace } from "../../shared/lib/workspace";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { WorkspaceChromeProvider, useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { useWorkspaceChromeState } from "../workspaces/useWorkspaceChromeState";
import { WorkspaceQuickSwitcher } from "../workspaces/WorkspaceQuickSwitcher";
import { UserMenu, type UserMenuItem } from "./components/UserMenu";
import { WorkspacePrimaryNav } from "./components/WorkspacePrimaryNav";
import { WorkspaceSectionNav } from "./components/WorkspaceSectionNav";
import { GlobalTopBar } from "./components/GlobalTopBar";
import { GlobalSearchBar } from "./components/GlobalSearchBar";

export function WorkspaceLayout() {
  const { workspace, workspaces } = useLoaderData<WorkspaceLoaderData>();
  const queryClient = useQueryClient();
  const chromeState = useWorkspaceChromeState(workspace.id);

  useEffect(() => {
    queryClient.setQueryData(workspaceKeys.list(), workspaces);
  }, [queryClient, workspaces]);

  useEffect(() => {
    writePreferredWorkspace(workspace);
  }, [workspace]);

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceChromeProvider
        isNavCollapsed={chromeState.isNavCollapsed}
        toggleNavCollapsed={chromeState.toggleNavCollapsed}
        setNavCollapsed={chromeState.setNavCollapsed}
        isSectionCollapsed={chromeState.isSectionCollapsed}
        toggleSectionCollapsed={chromeState.toggleSectionCollapsed}
        setSectionCollapsed={chromeState.setSectionCollapsed}
        isFocusMode={false}
        toggleFocusMode={() => undefined}
        setFocusMode={() => undefined}
      >
        <WorkspaceLayoutInner workspace={workspace} workspaces={workspaces}>
          <Outlet />
        </WorkspaceLayoutInner>
      </WorkspaceChromeProvider>
    </WorkspaceProvider>
  );
}

interface WorkspaceLayoutInnerProps {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: readonly WorkspaceProfile[];
  readonly children: ReactNode;
}

function WorkspaceLayoutInner({ workspace, workspaces, children }: WorkspaceLayoutInnerProps) {
  const session = useSession();
  const logoutMutation = useLogoutMutation();
  const navigate = useNavigate();
  const matches = useMatches();
  const location = useLocation();
  const { hasPermission } = useWorkspaceContext();
  const {
    isNavCollapsed,
    toggleNavCollapsed,
    isSectionCollapsed,
    toggleSectionCollapsed,
    inspector,
    closeInspector,
  } = useWorkspaceChrome();
  const [mobilePrimaryOpen, setMobilePrimaryOpen] = useState(false);
  const [mobileSectionOpen, setMobileSectionOpen] = useState(false);

  const activeSection = useMemo(() => matchWorkspaceSection(matches), [matches]);
  const breadcrumbs = useMemo(
    () => [workspace.name, activeSection.label],
    [workspace.name, activeSection.label],
  );

  useEffect(() => {
    setMobilePrimaryOpen(false);
    setMobileSectionOpen(false);
  }, [location.pathname, location.search]);

  const userPermissions = session.user.permissions ?? [];
  const canManageWorkspace =
    hasPermission("Workspace.Settings.ReadWrite") || userPermissions.includes("Workspaces.ReadWrite.All");
  const canManageAdmin = userPermissions.includes("System.Settings.ReadWrite");

  const handleSelectWorkspace = useCallback(
    (workspaceId: string) => {
      const target = workspaces.find((item) => item.id === workspaceId);
      navigate(buildWorkspaceSectionPath(target?.id ?? workspace.id, defaultWorkspaceSection.id));
    },
    [navigate, workspaces, workspace.id],
  );

  const handleOpenWorkspaceSettings = useCallback(() => {
    navigate(`/workspaces/${workspace.id}/settings`);
  }, [navigate, workspace.id]);

  const handleOpenAdmin = useCallback(() => {
    navigate("/settings");
  }, [navigate]);

  const profileMenuItems = useMemo<UserMenuItem[]>(() => {
    const items: UserMenuItem[] = [];
    if (canManageWorkspace) {
      items.push({
        id: "workspace-settings",
        label: "Workspace settings",
        description: "Members, permissions, integrations",
        onSelect: handleOpenWorkspaceSettings,
      });
    }
    if (canManageAdmin) {
      items.push({
        id: "admin-console",
        label: "Admin console",
        description: "Global preferences and controls",
        onSelect: handleOpenAdmin,
      });
    }
    return items;
  }, [canManageAdmin, canManageWorkspace, handleOpenAdmin, handleOpenWorkspaceSettings]);

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const showInspector = inspector.isOpen && Boolean(inspector.content);

  const topBarStart = (
    <>
      <button
        type="button"
        onClick={() => setMobilePrimaryOpen(true)}
        className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-white md:hidden"
        aria-label="Open navigation"
      >
        <MenuIcon />
      </button>
      <button
        type="button"
        onClick={toggleNavCollapsed}
        className={clsx(
          "hidden h-10 w-10 items-center justify-center rounded-lg border bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700 md:inline-flex",
          isNavCollapsed ? "border-brand-200 text-brand-700" : "border-slate-200",
        )}
        aria-pressed={isNavCollapsed}
        aria-label={isNavCollapsed ? "Expand navigation" : "Collapse navigation"}
      >
        <SidebarIcon collapsed={isNavCollapsed} />
      </button>
      <WorkspaceQuickSwitcher
        workspace={workspace}
        workspaces={workspaces}
        onSelectWorkspace={handleSelectWorkspace}
        onCreateWorkspace={() => navigate("/workspaces/new")}
        onManageWorkspace={handleOpenWorkspaceSettings}
        variant="brand"
        glyphOverride="ADE"
        title="Automatic Data Extractor"
        subtitle={workspace.name}
        showSlug={false}
      />
    </>
  );

  const topBarEnd = (
    <>
      <button
        type="button"
        className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700 lg:hidden"
        aria-label="Open section navigation"
        onClick={() => setMobileSectionOpen(true)}
      >
        <PanelsIcon />
      </button>
      <button
        type="button"
        className={clsx(
          "hidden h-10 w-10 items-center justify-center rounded-lg border bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700 lg:inline-flex",
          isSectionCollapsed ? "border-brand-200 text-brand-700" : "border-slate-200",
        )}
        onClick={toggleSectionCollapsed}
        aria-label={isSectionCollapsed ? "Expand section navigation" : "Collapse section navigation"}
        aria-pressed={isSectionCollapsed}
      >
        <PanelsIcon />
      </button>
      <button
        type="button"
        className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label="Open command palette (⌘K)"
      >
        <CommandIcon />
      </button>
      <button
        type="button"
        className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label="View notifications"
      >
        <BellIcon />
      </button>
      <button
        type="button"
        className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        aria-label="Open help center"
      >
        <HelpIcon />
      </button>
      <UserMenu
        displayName={displayName}
        email={email}
        items={profileMenuItems}
        onSignOut={() => logoutMutation.mutate()}
        isSigningOut={logoutMutation.isPending}
      />
    </>
  );

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <GlobalTopBar start={topBarStart} center={<GlobalSearchBar />} end={topBarEnd} />

      <div className="relative flex flex-1 overflow-hidden">
        <div className="hidden h-full md:flex">
          <WorkspacePrimaryNav
            workspace={workspace}
            collapsed={isNavCollapsed}
            onToggleCollapse={toggleNavCollapsed}
            onNavigate={() => setMobilePrimaryOpen(false)}
          />
        </div>

        <div className="hidden h-full lg:flex">
          <WorkspaceSectionNav
            workspaceId={workspace.id}
            section={activeSection}
            collapsed={isSectionCollapsed}
            onToggleCollapse={toggleSectionCollapsed}
            onNavigate={() => setMobileSectionOpen(false)}
          />
        </div>

        <main className="relative flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6">
            <WorkspaceContentSurface breadcrumbs={breadcrumbs}>{children}</WorkspaceContentSurface>
          </div>
        </main>

        {showInspector ? (
          <aside className="hidden xl:flex w-96 flex-shrink-0 flex-col border-l border-slate-200 bg-white p-4">
            <WorkspaceInspectorPanel inspector={inspector} onClose={closeInspector} />
          </aside>
        ) : null}
      </div>

      <MobilePanel side="left" open={mobilePrimaryOpen} onClose={() => setMobilePrimaryOpen(false)}>
        <WorkspacePrimaryNav
          workspace={workspace}
          collapsed={false}
          onToggleCollapse={toggleNavCollapsed}
          onNavigate={() => setMobilePrimaryOpen(false)}
          animatedWidth={false}
        />
      </MobilePanel>

      <MobilePanel side="right" open={mobileSectionOpen} onClose={() => setMobileSectionOpen(false)}>
        <WorkspaceSectionNav
          workspaceId={workspace.id}
          section={activeSection}
          collapsed={false}
          onToggleCollapse={toggleSectionCollapsed}
          onNavigate={() => setMobileSectionOpen(false)}
          animatedWidth={false}
        />
      </MobilePanel>

      {showInspector ? (
        <MobilePanel side="right" open onClose={closeInspector}>
          <div className="flex h-full flex-col p-4">
            <WorkspaceInspectorPanel inspector={inspector} onClose={closeInspector} />
          </div>
        </MobilePanel>
      ) : null}
    </div>
  );
}

function WorkspaceContentSurface({ breadcrumbs, children }: { readonly breadcrumbs: readonly string[]; readonly children: ReactNode }) {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <WorkspaceBreadcrumbs items={breadcrumbs} />
        <PageHeader breadcrumbs={breadcrumbs} />
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft focus:outline-none">{children}</div>
    </div>
  );
}

function WorkspaceBreadcrumbs({ items }: { readonly items: readonly string[] }) {
  if (items.length === 0) {
    return null;
  }
  return (
    <nav aria-label="Breadcrumb" className="text-xs font-semibold text-slate-500">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((item, index) => (
          <li key={`${item}-${index}`} className="flex items-center gap-1">
            {index > 0 ? <span className="text-slate-300" aria-hidden="true">/</span> : null}
            <span className={clsx(index === items.length - 1 && "text-slate-900")}>{item}</span>
          </li>
        ))}
      </ol>
    </nav>
  );
}

function PageHeader({ breadcrumbs }: { readonly breadcrumbs: readonly string[] }) {
  const title = breadcrumbs[breadcrumbs.length - 1] ?? "Workspace";
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        <p className="text-sm text-slate-500">All the controls and insights for this section live below.</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
        >
          <PlusIcon />
          <span>New action</span>
        </button>
      </div>
    </div>
  );
}

function WorkspaceInspectorPanel({
  inspector,
  onClose,
}: {
  readonly inspector: { title?: string; content: ReactNode | null };
  readonly onClose: () => void;
}) {
  if (!inspector.content) {
    return null;
  }
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-start justify-between border-b border-slate-200 pb-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{inspector.title ?? "Details"}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent text-slate-500 transition hover:border-slate-200 hover:text-slate-700"
          aria-label="Close inspector"
        >
          <CloseIcon />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">{inspector.content}</div>
    </div>
  );
}

function MobilePanel({
  side,
  open,
  onClose,
  children,
}: {
  readonly side: "left" | "right";
  readonly open: boolean;
  readonly onClose: () => void;
  readonly children: ReactNode;
}) {
  return (
    <div aria-hidden={!open}>
      <div
        className={clsx(
          "fixed inset-0 z-40 bg-slate-900/40 transition-opacity duration-300",
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />
      <div
        className={clsx(
          "fixed inset-y-0 z-50 flex w-72 max-w-[85vw] flex-col bg-white shadow-xl transition-transform duration-300",
          side === "left" ? "left-0" : "right-0",
          open
            ? "translate-x-0"
            : side === "left"
              ? "-translate-x-full"
              : "translate-x-full",
        )}
      >
        {children}
      </div>
    </div>
  );
}

function MenuIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path d="M3 5h14M3 10h14M3 15h14" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SidebarIcon({ collapsed }: { readonly collapsed: boolean }) {
  return collapsed ? (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M3 4h14v12H3z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9 4v12" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 10l-2 2m2-2l-2-2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ) : (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M3 4h14v12H3z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 4v12" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 10l2-2m-2 2l2 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PanelsIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <rect x="3" y="3" width="6" height="14" rx="1.2" />
      <rect x="11" y="3" width="6" height="8" rx="1.2" />
      <rect x="11" y="13" width="6" height="4" rx="1.2" />
    </svg>
  );
}

function CommandIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M7 3a3 3 0 0 0-3 3v1h3V3Zm6 0v4h3V6a3 3 0 0 0-3-3ZM4 13v1a3 3 0 1 0 3-3H4Zm9-2a3 3 0 1 0 3 3v-1h-3Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M7 7h6v6H7z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M10 17a2 2 0 0 0 2-2H8a2 2 0 0 0 2 2Zm6-5V9a6 6 0 0 0-12 0v3l-1 2h14l-1-2Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function HelpIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M10 18a8 8 0 1 0-8-8 8 8 0 0 0 8 8Zm0-5v.01M8.5 7.5a1.5 1.5 0 1 1 3 0c0 1-1.5 1.5-1.5 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M5 5l10 10M15 5l-10 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path d="M10 4v12M4 10h12" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

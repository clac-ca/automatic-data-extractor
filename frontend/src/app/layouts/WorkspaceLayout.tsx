import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Outlet, useLoaderData, useLocation, useMatches, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";

import { WorkspaceProvider, useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { workspaceKeys } from "../../features/workspaces/hooks/useWorkspacesQuery";
import type { WorkspaceLoaderData } from "../workspaces/loader";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import {
  buildWorkspaceSectionPath,
  defaultWorkspaceSection,
  matchWorkspaceSection,
  type WorkspaceSectionDescriptor,
} from "../workspaces/sections";
import { writePreferredWorkspace } from "../../shared/lib/workspace";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { WorkspaceChromeProvider, useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { useWorkspaceChromeState } from "../workspaces/useWorkspaceChromeState";
import { WorkspaceQuickSwitcher } from "../workspaces/WorkspaceQuickSwitcher";
import { UserMenu, type UserMenuItem } from "./components/UserMenu";
import { WorkspacePrimaryNav } from "./components/WorkspacePrimaryNav";
import { WorkspaceSectionNav } from "./components/WorkspaceSectionNav";

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
  const { isNavCollapsed, toggleNavCollapsed, inspector, closeInspector } = useWorkspaceChrome();

  const activeSection = useMemo(() => matchWorkspaceSection(matches), [matches]);
  const breadcrumbs = useMemo(
    () => [workspace.name, activeSection.label],
    [workspace.name, activeSection.label],
  );

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

  const [primaryDrawerOpen, setPrimaryDrawerOpen] = useState(false);
  const [sectionDrawerOpen, setSectionDrawerOpen] = useState(false);

  useEffect(() => {
    setPrimaryDrawerOpen(false);
    setSectionDrawerOpen(false);
  }, [location.pathname, location.search]);

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const showInspector = inspector.isOpen && Boolean(inspector.content);

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <WorkspaceTopBar
        workspace={workspace}
        workspaces={workspaces}
        collapsed={isNavCollapsed}
        onToggleCollapsed={toggleNavCollapsed}
        onOpenPrimaryDrawer={() => setPrimaryDrawerOpen(true)}
        onOpenSectionDrawer={() => setSectionDrawerOpen(true)}
        onSelectWorkspace={handleSelectWorkspace}
        onCreateWorkspace={() => navigate("/workspaces/new")}
        onOpenWorkspaceSettings={handleOpenWorkspaceSettings}
        profileMenuItems={profileMenuItems}
        displayName={displayName}
        email={email}
        onSignOut={() => logoutMutation.mutate()}
        isSigningOut={logoutMutation.isPending}
      />

      <div className="flex flex-1 overflow-hidden">
        <WorkspacePrimaryDrawer
          workspace={workspace}
          collapsed={isNavCollapsed}
          isDrawerOpen={primaryDrawerOpen}
          onCloseDrawer={() => setPrimaryDrawerOpen(false)}
        />

        <WorkspaceSectionDrawer
          workspaceId={workspace.id}
          section={activeSection}
          onCloseDrawer={() => setSectionDrawerOpen(false)}
        />

        <main className="relative flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6">
            <WorkspaceContentSurface breadcrumbs={breadcrumbs}>
              {children}
            </WorkspaceContentSurface>
          </div>
        </main>

        {showInspector ? (
          <aside className="hidden xl:flex w-96 flex-shrink-0 flex-col border-l border-slate-200 bg-white p-4">
            <WorkspaceInspectorPanel inspector={inspector} onClose={closeInspector} />
          </aside>
        ) : null}
      </div>

      {primaryDrawerOpen ? (
        <DrawerBackdrop onDismiss={() => setPrimaryDrawerOpen(false)} />
      ) : null}

      {sectionDrawerOpen ? (
        <DrawerBackdrop onDismiss={() => setSectionDrawerOpen(false)} />
      ) : null}

      {sectionDrawerOpen ? (
        <aside className="fixed inset-y-0 right-0 z-40 w-72 max-w-[85vw] border-l border-slate-200 bg-white shadow-xl lg:hidden">
          <WorkspaceSectionNav
            workspaceId={workspace.id}
            section={activeSection}
            onCloseDrawer={() => setSectionDrawerOpen(false)}
          />
        </aside>
      ) : null}

      {showInspector ? (
        <aside className="fixed inset-y-0 right-0 z-40 flex w-[min(90vw,360px)] flex-col border-l border-slate-200 bg-white p-4 shadow-xl xl:hidden">
          <WorkspaceInspectorPanel inspector={inspector} onClose={closeInspector} />
        </aside>
      ) : null}
    </div>
  );
}

function WorkspaceTopBar({
  workspace,
  workspaces,
  collapsed,
  onToggleCollapsed,
  onOpenPrimaryDrawer,
  onOpenSectionDrawer,
  onSelectWorkspace,
  onCreateWorkspace,
  onOpenWorkspaceSettings,
  profileMenuItems,
  displayName,
  email,
  onSignOut,
  isSigningOut,
}: {
  readonly workspace: WorkspaceProfile;
  readonly workspaces: readonly WorkspaceProfile[];
  readonly collapsed: boolean;
  readonly onToggleCollapsed: () => void;
  readonly onOpenPrimaryDrawer: () => void;
  readonly onOpenSectionDrawer: () => void;
  readonly onSelectWorkspace: (workspaceId: string) => void;
  readonly onCreateWorkspace: () => void;
  readonly onOpenWorkspaceSettings: () => void;
  readonly profileMenuItems: readonly UserMenuItem[];
  readonly displayName: string;
  readonly email: string;
  readonly onSignOut: () => void;
  readonly isSigningOut: boolean;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center gap-3 px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenPrimaryDrawer}
            className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-white md:hidden"
            aria-label="Open navigation"
          >
            <MenuIcon />
          </button>
          <button
            type="button"
            onClick={onToggleCollapsed}
            className="hidden h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-white md:inline-flex"
            aria-pressed={collapsed}
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          >
            <SidebarIcon collapsed={collapsed} />
          </button>
          <WorkspaceQuickSwitcher
            workspace={workspace}
            workspaces={workspaces}
            onSelectWorkspace={onSelectWorkspace}
            onCreateWorkspace={onCreateWorkspace}
            onManageWorkspace={onOpenWorkspaceSettings}
            variant="brand"
            glyphOverride="ADE"
            title="Automatic Data Extractor"
            subtitle={workspace.name}
            showSlug={false}
          />
        </div>

        <div className="flex flex-1 items-center justify-center px-4">
          <GlobalSearchBar />
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700"
            aria-label="Open workspace views"
            onClick={onOpenSectionDrawer}
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
            onSignOut={onSignOut}
            isSigningOut={isSigningOut}
          />
        </div>
      </div>
    </header>
  );
}

function WorkspacePrimaryDrawer({
  workspace,
  collapsed,
  isDrawerOpen,
  onCloseDrawer,
}: {
  readonly workspace: WorkspaceProfile;
  readonly collapsed: boolean;
  readonly isDrawerOpen: boolean;
  readonly onCloseDrawer: () => void;
}) {
  return (
    <>
      <div
        className={clsx("fixed inset-0 z-30 bg-slate-900/40 md:hidden", isDrawerOpen ? "block" : "hidden")}
        aria-hidden="true"
        onClick={onCloseDrawer}
      />
      <aside
        className={clsx(
          "fixed inset-y-0 left-0 z-40 flex w-72 max-w-[80vw] transform flex-col transition md:relative md:z-auto md:flex md:h-full md:w-auto md:max-w-none md:translate-x-0 md:border-r md:border-slate-200 md:bg-white",
          isDrawerOpen ? "translate-x-0 bg-white shadow-xl" : "-translate-x-full md:bg-white md:shadow-none",
        )}
      >
        <WorkspacePrimaryNav
          workspace={workspace}
          collapsed={collapsed && !isDrawerOpen}
          onCloseDrawer={onCloseDrawer}
          className={clsx(collapsed && "md:w-20")}
        />
      </aside>
    </>
  );
}

function WorkspaceSectionDrawer({
  workspaceId,
  section,
  onCloseDrawer,
}: {
  readonly workspaceId: string;
  readonly section: WorkspaceSectionDescriptor;
  readonly onCloseDrawer: () => void;
}) {
  return (
    <WorkspaceSectionNav workspaceId={workspaceId} section={section} onCloseDrawer={onCloseDrawer} className="hidden lg:flex" />
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
          className="focus-ring inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:border-slate-300"
          aria-label="Close inspector"
        >
          <CloseIcon />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto pr-1 text-sm text-slate-700">{inspector.content}</div>
    </div>
  );
}

function DrawerBackdrop({ onDismiss }: { readonly onDismiss: () => void }) {
  return (
    <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" aria-hidden="true" onClick={onDismiss} />
  );
}

function GlobalSearchBar() {
  const [value, setValue] = useState("");

  return (
    <form
      role="search"
      className="relative w-full max-w-xl"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <label htmlFor="workspace-global-search" className="sr-only">
        Search workspace
      </label>
      <input
        id="workspace-global-search"
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Search documents, runs, members, or actions…"
        className="w-full rounded-full border border-slate-200 bg-white px-5 py-3 pl-12 text-base text-slate-800 shadow-[0_12px_32px_rgba(15,23,42,0.08)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      />
      <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-slate-400">
        <SearchIcon />
      </span>
      <span className="pointer-events-none absolute inset-y-0 right-5 hidden items-center gap-1 text-xs text-slate-300 sm:flex">
        <kbd className="rounded border border-slate-200 px-1 py-0.5 font-sans text-[11px]">⌘</kbd>
        <kbd className="rounded border border-slate-200 px-1 py-0.5 font-sans text-[11px]">K</kbd>
      </span>
    </form>
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

function SearchIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path
        fillRule="evenodd"
        d="M8.5 3a5.5 5.5 0 013.934 9.35l3.108 3.107a1 1 0 01-1.414 1.415l-3.108-3.108A5.5 5.5 0 118.5 3zm0 2a3.5 3.5 0 100 7 3.5 3.5 0 000-7z"
        clipRule="evenodd"
      />
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

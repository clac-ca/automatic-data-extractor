import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Outlet, useLoaderData, useLocation, useMatches, useNavigate } from "react-router-dom";
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
import { WorkspaceHelpButton } from "../workspaces/WorkspaceHelpButton";
import { GlobalTopBar } from "./chrome/GlobalTopBar";
import { WorkspaceNavigationRail } from "./chrome/WorkspaceNavigationRail";
import { WorkspaceSectionSidebar } from "./chrome/WorkspaceSectionSidebar";
import { WorkspaceNavigationDrawer } from "./chrome/WorkspaceNavigationDrawer";
import { ProfileDropdown, type ProfileDropdownAction } from "./chrome/ProfileDropdown";
import { getWorkspaceSecondaryNavigation, type WorkspaceSecondaryNavigation } from "../workspaces/navigation";

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
  const [navigationOpen, setNavigationOpen] = useState(false);

  const activeSection = useMemo(() => matchWorkspaceSection(matches), [matches]);
  const sectionNavigation = useMemo(
    () => getWorkspaceSecondaryNavigation(workspace.id, activeSection),
    [workspace.id, activeSection.id, activeSection.label],
  );
  const breadcrumbs = useMemo(
    () => [workspace.name, activeSection.label],
    [workspace.name, activeSection.label],
  );

  useEffect(() => {
    setNavigationOpen(false);
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

  const profileMenuItems = useMemo<ProfileDropdownAction[]>(() => {
    const items: ProfileDropdownAction[] = [];
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

  const topBarLeading = (
    <div className="flex items-center gap-2">
      <TopBarButton
        icon={<MenuIcon />}
        label="Open navigation"
        className="lg:hidden"
        onClick={() => setNavigationOpen(true)}
      />
      <WorkspaceQuickSwitcher
        workspace={workspace}
        workspaces={workspaces}
        onSelectWorkspace={(workspaceId) => {
          handleSelectWorkspace(workspaceId);
          setNavigationOpen(false);
        }}
        onCreateWorkspace={() => navigate("/workspaces/new")}
        onManageWorkspace={handleOpenWorkspaceSettings}
        variant="brand"
        glyphOverride="ADE"
        title="Automatic Data Extractor"
        subtitle={workspace.name}
        showSlug={false}
      />
    </div>
  );

  const topBarCenter = <CommandLauncher />;

  const topBarTrailing = (
    <div className="flex items-center gap-2">
      <WorkspaceHelpButton />
      <ProfileDropdown
        displayName={displayName}
        email={email}
        actions={profileMenuItems}
        onSignOut={() => logoutMutation.mutate()}
        signingOut={logoutMutation.isPending}
      />
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <GlobalTopBar leading={topBarLeading} center={topBarCenter} trailing={topBarTrailing} />

      <div className="relative flex flex-1 overflow-hidden">
        <WorkspaceNavigationRail
          workspace={workspace}
          collapsed={isNavCollapsed}
          onToggleCollapse={toggleNavCollapsed}
          onNavigate={() => setNavigationOpen(false)}
        />

        <WorkspaceSectionSidebar
          section={activeSection}
          collapsed={isSectionCollapsed}
          onToggleCollapse={toggleSectionCollapsed}
          onNavigate={() => setNavigationOpen(false)}
          navigation={sectionNavigation}
        />

        <main className="relative flex-1 overflow-y-auto">
          <SectionNavigationBar
            section={activeSection}
            navigation={sectionNavigation}
            onNavigate={() => setNavigationOpen(false)}
          />
          <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6">
            <WorkspaceContentSurface breadcrumbs={breadcrumbs}>{children}</WorkspaceContentSurface>
          </div>
        </main>

        {showInspector ? (
          <aside className="hidden w-96 flex-shrink-0 flex-col border-l border-slate-200 bg-white p-4 xl:flex">
            <WorkspaceInspectorPanel inspector={inspector} onClose={closeInspector} />
          </aside>
        ) : null}
      </div>

      <WorkspaceNavigationDrawer
        open={navigationOpen}
        workspace={workspace}
        workspaces={workspaces}
        section={activeSection}
        navigation={sectionNavigation}
        onClose={() => setNavigationOpen(false)}
        onNavigate={() => setNavigationOpen(false)}
        onSelectWorkspace={handleSelectWorkspace}
        onCreateWorkspace={() => navigate("/workspaces/new")}
        onManageWorkspace={handleOpenWorkspaceSettings}
      />

      {showInspector ? (
        <InspectorOverlay onClose={closeInspector} title={inspector.title}>
          <WorkspaceInspectorPanel inspector={inspector} onClose={closeInspector} />
        </InspectorOverlay>
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
        <TopBarButton icon={<CloseIcon />} label="Close inspector" onClick={onClose} />
      </div>
      <div className="flex-1 overflow-y-auto">{inspector.content}</div>
    </div>
  );
}

function SectionNavigationBar({
  section,
  navigation,
  onNavigate,
}: {
  readonly section: WorkspaceSectionDescriptor;
  readonly navigation: WorkspaceSecondaryNavigation;
  readonly onNavigate?: () => void;
}) {
  if (navigation.status === "loading") {
    return (
      <div className="lg:hidden border-b border-slate-200 bg-white/95 px-4 py-3">
        <div className="flex gap-2">
          {Array.from({ length: 3 }).map((_, index) => (
            // eslint-disable-next-line react/no-array-index-key
            <div key={index} className="h-9 w-20 animate-pulse rounded-full bg-slate-100" />
          ))}
        </div>
      </div>
    );
  }

  if (navigation.items.length === 0) {
    return (
      <div className="lg:hidden border-b border-slate-200 bg-white/95 px-4 py-3 text-xs text-slate-500">
        {navigation.emptyLabel}
      </div>
    );
  }

  return (
    <nav
      aria-label={`${section.label} navigation`}
      className="lg:hidden border-b border-slate-200 bg-white/95 px-4"
    >
      <div className="flex flex-col gap-2 py-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{section.label}</div>
        <ul className="flex gap-2 overflow-x-auto" role="list">
          {navigation.items.map((item) => (
            <li key={item.id}>
              <NavLink
                to={item.href}
                onClick={() => onNavigate?.()}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center whitespace-nowrap rounded-full px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                    isActive
                      ? "bg-slate-900 text-white"
                      : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100",
                  )
                }
              >
                {item.label}
                {item.badge ? (
                  <span className="ml-2 inline-flex items-center rounded-full bg-slate-200 px-1.5 text-[0.7rem] font-semibold text-slate-600">
                    {item.badge}
                  </span>
                ) : null}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}

function CommandLauncher() {
  return (
    <button
      type="button"
      className="focus-ring hidden h-11 min-w-[16rem] items-center justify-between rounded-xl border border-slate-200 bg-white px-4 text-left text-sm font-medium text-slate-500 shadow-sm transition hover:border-brand-200 hover:text-slate-700 md:flex"
      aria-label="Open search (⌘K)"
    >
      <span className="inline-flex items-center gap-2">
        <SearchIcon />
        Search documents, jobs, and data
      </span>
      <span className="text-xs text-slate-400">⌘K</span>
    </button>
  );
}

function TopBarButton({
  icon,
  label,
  onClick,
  className,
}: {
  readonly icon: ReactNode;
  readonly label: string;
  readonly onClick: () => void;
  readonly className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-brand-200 hover:text-brand-700",
        className,
      )}
      aria-label={label}
    >
      {icon}
    </button>
  );
}

function InspectorOverlay({
  children,
  onClose,
  title,
}: {
  readonly children: ReactNode;
  readonly onClose: () => void;
  readonly title?: string;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-stretch justify-end bg-slate-900/30 backdrop-blur-sm lg:hidden" role="dialog" aria-modal="true" aria-label={title ?? "Inspector"}>
      <button type="button" className="flex-1" aria-label="Close inspector" onClick={onClose} />
      <div className="relative flex h-full w-[min(24rem,90vw)] flex-col border-l border-slate-200 bg-white p-4 shadow-2xl">
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

function CloseIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <path d="M5 5l10 10M15 5l-10 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx="9" cy="9" r="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m13.5 13.5 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Outlet, useLoaderData, useLocation, useMatches, useNavigate, useSearchParams } from "react-router-dom";
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
  workspaceSections,
  type WorkspaceSectionDescriptor,
} from "../workspaces/sections";
import { writePreferredWorkspace } from "../../shared/lib/workspace";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { WorkspaceChromeProvider, useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { useWorkspaceChromeState } from "../workspaces/useWorkspaceChromeState";
import { WorkspaceDocumentNav, WorkspaceQuickSwitcher, type DocumentViewMode } from "../workspaces/WorkspaceDocumentNav";
import { UserMenu, type UserMenuItem } from "./components/UserMenu";

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
        isFocusMode={chromeState.isFocusMode}
        toggleFocusMode={chromeState.toggleFocusMode}
        setFocusMode={chromeState.setFocusMode}
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
  const [searchParams] = useSearchParams();
  const { hasPermission } = useWorkspaceContext();
  const { isNavCollapsed, toggleNavCollapsed, inspector, closeInspector } = useWorkspaceChrome();

  const activeSection = useMemo(() => matchWorkspaceSection(matches), [matches]);

  const userPermissions = session.user.permissions ?? [];
  const canManageAdmin = userPermissions.includes("System.Settings.ReadWrite");
  const canManageWorkspace =
    hasPermission("Workspace.Settings.ReadWrite") || userPermissions.includes("Workspaces.ReadWrite.All");

  const documentsPath = buildWorkspaceSectionPath(workspace.id, "documents");

  const selectedDocumentId = searchParams.get("document");
  const currentViewParam =
    location.pathname.startsWith(documentsPath) ? searchParams.get("view") : null;
  const viewMode: DocumentViewMode =
    currentViewParam === "recent"
      ? "recent"
      : currentViewParam === "pinned"
        ? "pinned"
        : currentViewParam === "archived"
          ? "archived"
          : "all";

  const handleSelectDocument = useCallback(
    (documentId: string) => {
      const params = new URLSearchParams();
      if (viewMode !== "all") {
        params.set("view", viewMode);
      }
      params.set("document", documentId);
      navigate(`${documentsPath}?${params.toString()}`);
    },
    [documentsPath, navigate, viewMode],
  );

  const handleCreateDocument = useCallback(() => {
    navigate(`${documentsPath}?view=new`);
  }, [documentsPath, navigate]);

  const handleCreateWorkspace = useCallback(() => {
    navigate("/workspaces/new");
  }, [navigate]);

  const handleManageWorkspace = useCallback(() => {
    navigate(`/workspaces/${workspace.id}/settings`);
  }, [navigate, workspace.id]);

  const handleSelectWorkspace = useCallback(
    (workspaceId: string) => {
      const target = workspaces.find((item) => item.id === workspaceId);
      if (!target) {
        return;
      }
      navigate(buildWorkspaceSectionPath(target.id, defaultWorkspaceSection.id));
    },
    [navigate, workspaces],
  );

  const handleOpenAdmin = useCallback(() => {
    navigate("/settings");
  }, [navigate]);

  const breadcrumbs = useMemo(
    () => [workspace.name, activeSection.label],
    [workspace.name, activeSection.label],
  );

  const canCreateWorkspace = userPermissions.includes("Workspaces.Create");

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const profileMenuItems = useMemo<UserMenuItem[]>(() => {
    const items: UserMenuItem[] = [];
    if (canManageWorkspace) {
      items.push({
        id: "profile-workspace-settings",
        label: "Workspace settings",
        description: "Members, permissions, and integrations",
        onSelect: handleManageWorkspace,
      });
    }
    if (canManageAdmin) {
      items.push({
        id: "profile-admin-console",
        label: "Admin console",
        description: "Global controls and system preferences",
        onSelect: handleOpenAdmin,
      });
    }
    if (canCreateWorkspace) {
      items.push({
        id: "profile-new-workspace",
        label: "Create workspace",
        description: "Spin up a new workspace",
        onSelect: handleCreateWorkspace,
      });
    }
    return items;
  }, [
    canCreateWorkspace,
    canManageAdmin,
    canManageWorkspace,
    handleCreateWorkspace,
    handleManageWorkspace,
    handleOpenAdmin,
  ]);

  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname, location.search]);

  const leftRailCollapsed = isNavCollapsed;
  const showInspector = inspector.isOpen && Boolean(inspector.content);

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-3 px-4 py-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-white md:hidden"
              aria-label="Open document navigation"
            >
              <MenuIcon />
            </button>
            <button
              type="button"
              onClick={toggleNavCollapsed}
              className="hidden h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-slate-300 hover:bg-white md:inline-flex"
              aria-pressed={leftRailCollapsed}
              aria-label={leftRailCollapsed ? "Expand document navigation" : "Collapse document navigation"}
            >
              <SidebarIcon collapsed={leftRailCollapsed} />
            </button>
            <WorkspaceQuickSwitcher
              workspace={workspace}
              workspaces={workspaces}
              onSelectWorkspace={handleSelectWorkspace}
              onCreateWorkspace={canCreateWorkspace ? handleCreateWorkspace : undefined}
              onManageWorkspace={canManageWorkspace ? handleManageWorkspace : undefined}
              variant="brand"
              glyphOverride="ADE"
              title="Automatic Data Extractor"
              subtitle={workspace.name}
              showSlug={false}
            />
          </div>

          <div className="flex flex-1 justify-center px-4">
            <WorkspaceGlobalSearchBar />
          </div>

          <div className="flex items-center gap-2">
            <UserMenu
              displayName={displayName}
              email={email}
              items={profileMenuItems}
              onSignOut={() => logoutMutation.mutate()}
              isSigningOut={logoutMutation.isPending}
            />
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div
          className={clsx("fixed inset-0 z-30 bg-slate-900/40 md:hidden", mobileNavOpen ? "block" : "hidden")}
          aria-hidden="true"
          onClick={() => setMobileNavOpen(false)}
        />
        <aside
          className={clsx(
            "fixed inset-y-0 left-0 z-40 flex w-72 max-w-[80vw] transform flex-col bg-white shadow-xl transition md:relative md:z-auto md:flex md:h-full md:border-r md:border-slate-200 md:bg-white md:shadow-none",
            mobileNavOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
            leftRailCollapsed ? "md:w-20" : "md:w-72",
          )}
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 md:hidden">
            <span className="text-sm font-semibold text-slate-700">Documents</span>
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:border-slate-300"
              aria-label="Close navigation"
            >
              <CloseIcon />
            </button>
          </div>
          <div
            className={clsx(
              "flex-1 overflow-y-auto px-4 py-4",
              leftRailCollapsed ? "md:px-2 md:py-4" : "md:px-4 md:py-6",
            )}
          >
            <WorkspaceDocumentNav
              workspaceId={workspace.id}
              selectedDocumentId={selectedDocumentId}
              onSelectDocument={handleSelectDocument}
              onCreateDocument={handleCreateDocument}
              collapsed={leftRailCollapsed && !mobileNavOpen}
            />
          </div>
        </aside>

        <main className="relative flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-7xl flex-col px-4 py-6">
            <WorkspaceContentSurface
              workspaceId={workspace.id}
              activeSectionId={activeSection.id}
              breadcrumbs={breadcrumbs}
            >
              {children}
            </WorkspaceContentSurface>
          </div>
        </main>

        {showInspector ? (
          <aside className="hidden xl:flex w-80 flex-col border-l border-slate-200 bg-white p-4">
            <InspectorPanel inspector={inspector} onClose={closeInspector} />
          </aside>
        ) : null}
      </div>

      {showInspector ? (
        <>
          <div className="fixed inset-0 z-30 bg-slate-900/40 xl:hidden" aria-hidden="true" onClick={closeInspector} />
          <aside className="fixed inset-y-0 right-0 z-40 flex w-[min(90vw,360px)] flex-col border-l border-slate-200 bg-white p-4 shadow-xl xl:hidden">
            <InspectorPanel inspector={inspector} onClose={closeInspector} />
          </aside>
        </>
      ) : null}
    </div>
  );
}

const workspaceTabOrder = ["documents", "configurations", "members", "settings", "jobs"] as const;

function WorkspaceSectionTabs({
  workspaceId,
  activeSectionId,
}: {
  readonly workspaceId: string;
  readonly activeSectionId: WorkspaceSectionDescriptor["id"];
}) {
  const sections = workspaceTabOrder
    .map((sectionId) => workspaceSections.find((section) => section.id === sectionId))
    .filter((section): section is WorkspaceSectionDescriptor => Boolean(section));

  return (
    <nav className="flex min-w-0 overflow-x-auto" aria-label="Workspace sections">
      <ul className="flex min-w-full gap-1 overflow-x-auto whitespace-nowrap rounded-full border border-slate-200 bg-white/80 px-2 py-1 shadow-[0_1px_2px_rgba(15,23,42,0.08)]">
        {sections.map((section) => {
          const href = buildWorkspaceSectionPath(workspaceId, section.id);
          return (
            <li key={section.id} className="flex-shrink-0">
              <NavLink
                to={href}
                className={({ isActive }) =>
                  clsx(
                    "inline-flex items-center rounded-full px-4 py-1.5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
                    isActive || section.id === activeSectionId
                      ? "bg-brand-600 text-white shadow-md"
                      : "text-slate-600 hover:bg-white",
                  )
                }
              >
                {section.label}
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function InspectorPanel({
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

function MenuIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
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

interface WorkspaceContentSurfaceProps {
  readonly workspaceId: string;
  readonly activeSectionId: WorkspaceSectionDescriptor["id"];
  readonly breadcrumbs: readonly string[];
  readonly children: ReactNode;
}

function WorkspaceContentSurface({ workspaceId, activeSectionId, breadcrumbs, children }: WorkspaceContentSurfaceProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <WorkspaceBreadcrumbs items={breadcrumbs} />
        <WorkspaceSectionTabs workspaceId={workspaceId} activeSectionId={activeSectionId} />
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft focus:outline-none">
        {children}
      </div>
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

function WorkspaceGlobalSearchBar() {
  const [value, setValue] = useState("");

  return (
    <form
      role="search"
      className="relative w-full max-w-xl"
      onSubmit={(event) => {
        event.preventDefault();
        // TODO: wire search behavior
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
        placeholder="Search documents, configurations, members…"
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

import { useEffect, useMemo } from "react";
import type { ReactNode } from "react";
import { Outlet, useLoaderData, useMatches, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { WorkspaceProvider, useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { workspaceKeys } from "../../features/workspaces/hooks/useWorkspacesQuery";
import type { WorkspaceLoaderData } from "../workspaces/loader";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import {
  buildWorkspaceSectionPath,
  defaultWorkspaceSection,
  matchWorkspaceSection,
} from "../workspaces/sections";
import { writePreferredWorkspace } from "../../shared/lib/workspace";
import { AppShell, type AppShellNavItem, type AppShellProfileMenuItem } from "./AppShell";
import { Button } from "../../ui";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { WorkspaceChromeProvider, useWorkspaceChrome } from "../workspaces/WorkspaceChromeContext";
import { useWorkspaceChromeState } from "../workspaces/useWorkspaceChromeState";
import {
  DocumentsIcon,
  RecentIcon,
  PinIcon,
  ArchiveIcon,
  SettingsIcon,
} from "../workspaces/icons";

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
  const { hasPermission } = useWorkspaceContext();
  const {
    isNavCollapsed,
    toggleNavCollapsed,
    isFocusMode,
    toggleFocusMode,
    inspector,
    closeInspector,
  } = useWorkspaceChrome();

  const activeSection = useMemo(() => matchWorkspaceSection(matches), [matches]);

  const userPermissions = session.user.permissions ?? [];
  const canManageAdmin = userPermissions.includes("System.Settings.ReadWrite");
  const canManageWorkspace =
    hasPermission("Workspace.Settings.ReadWrite") || userPermissions.includes("Workspaces.ReadWrite.All");

  const documentsPath = buildWorkspaceSectionPath(workspace.id, "documents");

  const navItems = useMemo<readonly AppShellNavItem[]>(
    () => [
      {
        id: "documents-all",
        label: "All documents",
        description: "Every upload in this workspace",
        to: documentsPath,
        icon: <DocumentsIcon className="h-5 w-5" />,
        kind: "primary",
      },
      {
        id: "documents-recent",
        label: "Recent",
        description: "Sorted by latest activity",
        to: `${documentsPath}?view=recent`,
        icon: <RecentIcon className="h-5 w-5" />,
        kind: "primary",
      },
      {
        id: "documents-pinned",
        label: "Pinned",
        description: "Documents you pinned for quick access",
        to: `${documentsPath}?view=pinned`,
        icon: <PinIcon className="h-5 w-5" />,
        kind: "primary",
      },
      {
        id: "documents-archived",
        label: "Archived",
        description: "Uploads kept for reference",
        to: `${documentsPath}?view=archived`,
        icon: <ArchiveIcon className="h-5 w-5" />,
        kind: "primary",
      },
    ],
    [documentsPath],
  );

  const breadcrumbs = useMemo(
    () => [workspace.name, activeSection.label],
    [workspace.name, activeSection.label],
  );

  const canCreateWorkspace = userPermissions.includes("Workspaces.Create");

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  const topBarActions = (
    <div className="flex items-center gap-3">
      <WorkspaceSwitcher
        workspaces={workspaces}
        activeWorkspace={workspace}
        onSelect={(target) => navigate(buildWorkspaceSectionPath(target.id, defaultWorkspaceSection.id))}
      />
      {canCreateWorkspace ? (
        <Button
          size="sm"
          variant="primary"
          onClick={() => navigate(`${documentsPath}?view=new`)}
          className="hidden md:inline-flex"
        >
          New document
        </Button>
      ) : null}
      {canCreateWorkspace ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => navigate(`${documentsPath}?view=new`)}
          className="md:hidden"
        >
          New doc
        </Button>
      ) : null}
      <Button
        size="sm"
        variant={isFocusMode ? "primary" : "ghost"}
        className="md:hidden"
        onClick={() => {
          if (!isFocusMode && inspector.isOpen) {
            closeInspector();
          }
          toggleFocusMode();
        }}
        aria-pressed={isFocusMode}
      >
        {isFocusMode ? "Exit focus" : "Focus"}
      </Button>
    </div>
  );

  const workspaceSummary = useMemo(
    () => ({
      name: workspace.name,
      description: workspace.slug ? `Slug • ${workspace.slug}` : undefined,
      tag: workspace.is_default ? { label: "Default", tone: "brand" as const } : undefined,
      onManage: canManageWorkspace
        ? () => navigate(`/workspaces/${workspace.id}/settings`)
        : undefined,
    }),
    [canManageWorkspace, navigate, workspace.name, workspace.slug, workspace.id, workspace.is_default],
  );

  const profileMenuItems = useMemo(() => {
    const items = [] as AppShellProfileMenuItem[];
    if (canManageWorkspace) {
      items.push({
        id: "profile-workspace-settings",
        label: "Workspace settings",
        description: "Members, permissions, and integrations",
        onSelect: () => navigate(`/workspaces/${workspace.id}/settings`),
        icon: <SettingsIcon className="h-4 w-4" />,
      });
    }
    if (canManageAdmin) {
      items.push({
        id: "profile-admin-console",
        label: "Admin console",
        description: "Global controls and system preferences",
        onSelect: () => navigate("/settings"),
        icon: <SettingsIcon className="h-4 w-4" />,
      });
    }
    if (canCreateWorkspace) {
      items.push({
        id: "profile-new-workspace",
        label: "Create workspace",
        description: "Spin up a new workspace",
        onSelect: () => navigate("/workspaces/new"),
      });
    }
    return items;
  }, [canCreateWorkspace, canManageAdmin, canManageWorkspace, navigate, workspace.id]);

  return (
    <AppShell
      brand={{
        label: "Automatic Data Extractor",
        subtitle: workspace.name,
        onClick: () => navigate(buildWorkspaceSectionPath(workspace.id, defaultWorkspaceSection.id)),
      }}
      breadcrumbs={breadcrumbs}
      navItems={navItems}
      workspaceSummary={workspaceSummary}
      isLeftRailCollapsed={isNavCollapsed}
      onToggleLeftRail={toggleNavCollapsed}
      isFocusMode={isFocusMode}
      onToggleFocusMode={toggleFocusMode}
      topBarActions={topBarActions}
      profileMenuItems={profileMenuItems}
      user={{ displayName, email }}
      onSignOut={() => logoutMutation.mutate()}
      isSigningOut={logoutMutation.isPending}
      rightInspector={
        inspector.content
          ? {
              title: inspector.title,
              content: inspector.content,
              isOpen: inspector.isOpen,
              onClose: closeInspector,
            }
          : undefined
      }
    >
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft focus:outline-none">
        {children}
      </div>
    </AppShell>
  );
}

function WorkspaceSwitcher({
  workspaces,
  activeWorkspace,
  onSelect,
}: {
  readonly workspaces: readonly WorkspaceProfile[];
  readonly activeWorkspace: WorkspaceProfile;
  readonly onSelect: (workspace: WorkspaceProfile) => void;
}) {
  if (workspaces.length === 0) {
    return null;
  }

  return (
    <div className="relative">
      <label htmlFor="workspace-selector" className="sr-only">
        Select workspace
      </label>
      <select
        id="workspace-selector"
        value={activeWorkspace.id}
        onChange={(event) => {
          const selected = workspaces.find((item) => item.id === event.target.value);
          if (selected) {
            onSelect(selected);
          }
        }}
        className="appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2 pr-8 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        aria-label="Change workspace"
      >
        {workspaces.map((workspaceOption) => (
          <option key={workspaceOption.id} value={workspaceOption.id}>
            {workspaceOption.name}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-slate-400">
        ▾
      </span>
    </div>
  );
}

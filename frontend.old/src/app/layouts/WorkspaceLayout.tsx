import { useEffect, useMemo } from "react";
import type { ReactNode } from "react";
import { Outlet, useLoaderData, useMatches, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { WorkspaceProvider, useWorkspaceContext } from "../../features/workspaces/context/WorkspaceContext";
import { workspaceKeys } from "../../features/workspaces/hooks/useWorkspacesQuery";
import { WorkspaceDocumentRail } from "../../features/documents/components/WorkspaceDocumentRail";
import type { WorkspaceLoaderData } from "../workspaces/loader";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import {
  buildWorkspaceSectionPath,
  defaultWorkspaceSection,
  matchWorkspaceSection,
  workspaceSections,
} from "../workspaces/sections";
import { writePreferredWorkspace } from "../../shared/lib/workspace";
import { Button } from "../../ui";
import { AppShell, type AppShellNavItem, type AppShellProfileMenuItem } from "./AppShell";
import { useSession } from "../../features/auth/context/SessionContext";
import { useLogoutMutation } from "../../features/auth/hooks/useLogoutMutation";
import { useWorkspaceRailState } from "../workspaces/useWorkspaceRailState";

export function WorkspaceLayout() {
  const { workspace, workspaces } = useLoaderData<WorkspaceLoaderData>();
  const queryClient = useQueryClient();
  const railState = useWorkspaceRailState(workspace.id);

  useEffect(() => {
    queryClient.setQueryData(workspaceKeys.list(), workspaces);
  }, [queryClient, workspaces]);

  useEffect(() => {
    writePreferredWorkspace(workspace);
  }, [workspace]);

  return (
    <WorkspaceProvider workspace={workspace} workspaces={workspaces}>
      <WorkspaceDetailLayout
        drawerCollapsed={railState.isCollapsed}
        onToggleDrawer={railState.toggleCollapse}
        pinnedDocumentIds={railState.pinnedDocumentIds}
        onTogglePin={railState.setPinned}
      >
        <Outlet />
      </WorkspaceDetailLayout>
    </WorkspaceProvider>
  );
}

interface WorkspaceDetailLayoutProps {
  readonly children: ReactNode;
  readonly drawerCollapsed: boolean;
  readonly onToggleDrawer: () => void;
  readonly pinnedDocumentIds: readonly string[];
  readonly onTogglePin: (documentId: string, nextPinned: boolean) => void;
}

function WorkspaceDetailLayout({
  children,
  drawerCollapsed,
  onToggleDrawer,
  pinnedDocumentIds,
  onTogglePin,
}: WorkspaceDetailLayoutProps) {
  const { workspace, workspaces, hasPermission } = useWorkspaceContext();
  const session = useSession();
  const logoutMutation = useLogoutMutation();
  const navigate = useNavigate();
  const matches = useMatches();

  const activeSection = useMemo(() => matchWorkspaceSection(matches), [matches]);

  const navItems = useMemo<AppShellNavItem[]>(
    () =>
      workspaceSections.map((section) => ({
        label: section.label,
        to: buildWorkspaceSectionPath(workspace.id, section.id),
        end: section.id === defaultWorkspaceSection.id,
      })),
    [workspace.id],
  );

  const breadcrumbs = useMemo(() => [workspace.name, activeSection.label], [workspace.name, activeSection.label]);

  const userPermissions = session.user.permissions ?? [];
  const canCreateWorkspace = userPermissions.includes("Workspaces.Create");
  const canManageAdmin = userPermissions.includes("System.Settings.ReadWrite");
  const canManageWorkspace =
    hasPermission("Workspace.Settings.ReadWrite") || userPermissions.includes("Workspaces.ReadWrite.All");

  const profileMenuItems: AppShellProfileMenuItem[] = useMemo(() => {
    const items: AppShellProfileMenuItem[] = [];
    if (canManageWorkspace) {
      items.push({
        type: "nav",
        label: "Workspace settings",
        to: buildWorkspaceSectionPath(workspace.id, "settings"),
      });
    }
    if (canManageAdmin) {
      items.push({ type: "nav", label: "Admin settings", to: "/settings" });
    }
    return items;
  }, [canManageAdmin, canManageWorkspace, workspace.id]);

  const leading = (
    <WorkspaceSwitcher
      workspaces={workspaces}
      activeWorkspace={workspace}
      onSelect={(target) => navigate(buildWorkspaceSectionPath(target.id, defaultWorkspaceSection.id))}
      onCreate={() => navigate("/workspaces/new")}
      canCreate={canCreateWorkspace}
    />
  );

  const actions = canCreateWorkspace ? (
    <Button variant="primary" onClick={() => navigate("/workspaces/new")}>New workspace</Button>
  ) : undefined;

  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <AppShell
      brand={{
        label: "Automatic Data Extractor",
        subtitle: workspace.name,
        onClick: () => navigate(buildWorkspaceSectionPath(workspace.id, defaultWorkspaceSection.id)),
      }}
      breadcrumbs={breadcrumbs}
      navItems={navItems}
      leading={leading}
      actions={actions}
      sidebar={{
        content: (
          <WorkspaceDocumentRail
            workspaceId={workspace.id}
            collapsed={drawerCollapsed}
            onToggleCollapse={onToggleDrawer}
            onCreateDocument={() => navigate(buildWorkspaceSectionPath(workspace.id, "documents"))}
            onSelectDocument={(documentId) =>
              navigate(`${buildWorkspaceSectionPath(workspace.id, "documents")}?document=${documentId}`)
            }
            pinnedDocumentIds={pinnedDocumentIds}
            onTogglePin={onTogglePin}
          />
        ),
        width: 280,
        collapsedWidth: 72,
        isCollapsed: drawerCollapsed,
      }}
      profileMenuItems={profileMenuItems}
      user={{ displayName, email }}
      onSignOut={() => logoutMutation.mutate()}
      isSigningOut={logoutMutation.isPending}
    >
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">{children}</div>
    </AppShell>
  );
}

interface WorkspaceSwitcherProps {
  workspaces: readonly WorkspaceProfile[];
  activeWorkspace: WorkspaceProfile;
  onSelect: (workspace: WorkspaceProfile) => void;
  onCreate: () => void;
  canCreate: boolean;
}

function WorkspaceSwitcher({ workspaces, activeWorkspace, onSelect, onCreate, canCreate }: WorkspaceSwitcherProps) {
  if (workspaces.length === 0) {
    return null;
  }

  const createValue = "__create_workspace__";

  return (
    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
      Workspace
      <select
        value={activeWorkspace.id}
        onChange={(event) => {
          const selected = event.target.value;
          if (selected === createValue) {
            onCreate();
            return;
          }
          const next = workspaces.find((workspace) => workspace.id === selected);
          if (next) {
            onSelect(next);
          }
        }}
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-medium text-slate-700 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
      >
        {workspaces.map((workspace) => (
          <option key={workspace.id} value={workspace.id}>
            {workspace.name}
          </option>
        ))}
        {canCreate ? <option value={createValue}>+ Create workspace</option> : null}
      </select>
    </label>
  );
}

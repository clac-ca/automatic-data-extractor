import { useEffect, useMemo, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

import { useSessionQuery } from "../../features/auth/hooks/useSessionQuery";
import { useWorkspacesQuery } from "../../features/workspaces/hooks/useWorkspacesQuery";
import type { WorkspaceProfile } from "../../shared/types/workspaces";
import { createScopedStorage } from "../../shared/lib/storage";
import { writePreferredWorkspace } from "../../shared/lib/workspace";
import { Button } from "../../ui";
import { AppShell, type AppShellNavItem, type AppShellProfileMenuItem } from "./AppShell";
import { DocumentDrawer } from "../components/DocumentDrawer";
import { PageState } from "../components/PageState";

type HeaderNavKey = "documents" | "jobs" | "configurations" | "members" | "settings";

const NAV_LINKS: Array<{ key: HeaderNavKey; label: string; description: string }> = [
  { key: "documents", label: "Documents", description: "Uploads, processing status, download history" },
  { key: "jobs", label: "Jobs", description: "Extraction queues and run history" },
  { key: "configurations", label: "Configurations", description: "Document type rules and deployment" },
  { key: "members", label: "Members", description: "Invite teammates, manage roles" },
  { key: "settings", label: "Settings", description: "Workspace preferences and integrations" },
];

const SECTION_LABELS: Record<string, string> = {
  documents: "Documents",
  jobs: "Jobs",
  configurations: "Configurations",
  members: "Members",
  settings: "Settings",
};

const storage = createScopedStorage("ade.active_workspace");

export function WorkspaceLayout() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { session } = useSessionQuery();
  const userPermissions = session?.user.permissions ?? [];

  if (!workspaceId) {
    return <Navigate to="/workspaces" replace />;
  }

  const workspacesQuery = useWorkspacesQuery();

  if (workspacesQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState title="Loading workspace" variant="loading" />
      </div>
    );
  }

  if (workspacesQuery.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <PageState
          title="Unable to load workspaces"
          description="Refresh the page or try again later."
          variant="error"
          action={
            <Button variant="secondary" onClick={() => workspacesQuery.refetch()}>
              Try again
            </Button>
          }
        />
      </div>
    );
  }

  const workspaces = workspacesQuery.data ?? [];
  if (workspaces.length === 0) {
    return <Navigate to="/workspaces" replace />;
  }

  const activeWorkspace =
    workspaces.find((workspace) => workspace.id === workspaceId) ?? workspaces[0] ?? null;

  if (!activeWorkspace) {
    return <Navigate to="/workspaces" replace />;
  }

  useEffect(() => {
    storage.set(activeWorkspace.id);
    writePreferredWorkspace(activeWorkspace);
  }, [activeWorkspace]);

  const canCreateWorkspace = userPermissions.includes("Workspaces.Create");
  const canManageWorkspace = userPermissions.includes("Workspaces.ReadWrite.All");
  const canManageAdmin = userPermissions.includes("System.Settings.ReadWrite");

  const navItems: AppShellNavItem[] = useMemo(
    () =>
      NAV_LINKS.map((link) => ({
        label: link.label,
        to: `/workspaces/${workspaceId}/${link.key}`,
        end: link.key === "documents",
      })),
    [workspaceId],
  );

  const profileMenuItems: AppShellProfileMenuItem[] = useMemo(() => {
    const items: AppShellProfileMenuItem[] = [];
    if (canManageWorkspace) {
      items.push({
        type: "nav",
        label: "Workspace settings",
        to: `/workspaces/${workspaceId}/settings`,
      });
    }
    if (canManageAdmin) {
      items.push({ type: "nav", label: "Admin settings", to: "/settings" });
    }
    return items;
  }, [canManageAdmin, canManageWorkspace, workspaceId]);

  const activeSection = useMemo<HeaderNavKey>(() => {
    const [, , , section] = location.pathname.split("/");
    if (!section || !NAV_LINKS.find((link) => link.key === section)) {
      return "documents";
    }
    return section as HeaderNavKey;
  }, [location.pathname]);

  const breadcrumbs = useMemo(
    () => getBreadcrumbSegments(activeWorkspace.name, activeSection),
    [activeWorkspace.name, activeSection],
  );

  const leading = (
    <WorkspaceSwitcher
      workspaces={workspaces}
      activeWorkspace={activeWorkspace}
      onSelect={(workspace) => navigate(`/workspaces/${workspace.id}/documents`)}
      onCreate={() => navigate("/workspaces/new")}
      canCreate={canCreateWorkspace}
    />
  );

  const actions = canCreateWorkspace ? (
    <Button variant="primary" onClick={() => navigate("/workspaces/new")}>
      New workspace
    </Button>
  ) : undefined;

  const [drawerCollapsed, setDrawerCollapsed] = useState(false);

  const sidebar = {
    content: (
      <DocumentDrawer
        workspaceId={workspaceId}
        collapsed={drawerCollapsed}
        onToggleCollapse={() => setDrawerCollapsed((value) => !value)}
        onCreateDocument={() => navigate(`/workspaces/${workspaceId}/documents`)}
        onSelectDocument={(documentId) => navigate(`/workspaces/${workspaceId}/documents?document=${documentId}`)}
      />
    ),
    width: 280,
    collapsedWidth: 72,
    isCollapsed: drawerCollapsed,
  } as const;

  return (
    <AppShell
      brand={{
        label: "Automatic Data Extractor",
        subtitle: activeWorkspace.name,
        onClick: () => navigate(`/workspaces/${workspaceId}/documents`),
      }}
      breadcrumbs={breadcrumbs}
      navItems={navItems}
      leading={leading}
      actions={actions}
      sidebar={sidebar}
      profileMenuItems={profileMenuItems}
    >
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-soft">
        <Outlet />
      </div>
    </AppShell>
  );
}

function WorkspaceSwitcher({
  workspaces,
  activeWorkspace,
  onSelect,
  onCreate,
  canCreate,
}: {
  workspaces: WorkspaceProfile[];
  activeWorkspace: WorkspaceProfile;
  onSelect: (workspace: WorkspaceProfile) => void;
  onCreate: () => void;
  canCreate: boolean;
}) {
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

function getBreadcrumbSegments(workspaceName: string, section: HeaderNavKey) {
  const sectionLabel = SECTION_LABELS[section] ?? section.charAt(0).toUpperCase() + section.slice(1);
  return [workspaceName, sectionLabel];
}

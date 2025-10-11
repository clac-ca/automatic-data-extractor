import { useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";

import type { SessionEnvelope, WorkspaceProfile } from "../../../shared/api/types";
import { useWorkspacesQuery } from "../hooks/useWorkspacesQuery";
import { WorkspaceChrome } from "../layout/WorkspaceChrome";
import { WorkspaceChromeProvider } from "../layout/WorkspaceChromeContext";
import { WorkspaceRail } from "../layout/WorkspaceRail";
import { WorkspaceTopBar } from "./WorkspaceTopBar";
import { WorkspaceCanvasHeader } from "./WorkspaceCanvasHeader";
import { WorkspaceCanvasNavigation } from "./WorkspaceCanvasNavigation";
import { WorkspaceEmptyState } from "./WorkspaceEmptyState";
import { CreateWorkspaceDialog } from "./CreateWorkspaceDialog";
import { RBAC } from "../../../shared/rbac/permissions";
import { globalCan } from "../../../shared/rbac/can";
import type { WorkspaceNavItemConfig } from "../utils/navigation";
import { resolveWorkspaceNavLink } from "../utils/navigation";

export interface WorkspaceLayoutContext {
  workspace?: WorkspaceProfile;
}

const NAVIGATION: WorkspaceNavItemConfig[] = [
  { id: "overview", label: "Overview", to: ".", end: true },
  {
    id: "documents",
    label: "Documents",
    to: "documents",
    requiredPermission: RBAC.Workspace.Documents.Read,
  },
  {
    id: "jobs",
    label: "Jobs",
    to: "jobs",
    requiredPermission: RBAC.Workspace.Jobs.Read,
  },
  {
    id: "configurations",
    label: "Configurations",
    to: "configurations",
    requiredPermission: RBAC.Workspace.Configurations.Read,
  },
  {
    id: "members",
    label: "Members",
    to: "members",
    requiredPermission: RBAC.Workspace.Members.Read,
  },
  {
    id: "roles",
    label: "Roles",
    to: "roles",
    requiredPermission: RBAC.Workspace.Roles.Read,
  },
  {
    id: "settings",
    label: "Settings",
    to: "settings",
    requiredPermission: RBAC.Workspace.Settings.ReadWrite,
  },
];

export function WorkspaceLayout() {
  const { data: workspacesData, isLoading, error } = useWorkspacesQuery();
  const session = useOutletContext<SessionEnvelope>();
  const navigate = useNavigate();
  const params = useParams<{ workspaceId?: string }>();
  const location = useLocation();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const lastFocusedElementRef = useRef<HTMLElement | null>(null);

  const captureFocus = () => {
    lastFocusedElementRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
  };

  const restoreFocus = () => {
    const element = lastFocusedElementRef.current;
    lastFocusedElementRef.current = null;
    if (element) {
      window.setTimeout(() => {
        element.focus();
      }, 0);
    }
  };

  const openCreateWorkspaceDialog = () => {
    captureFocus();
    setIsCreateDialogOpen(true);
  };

  const closeCreateWorkspaceDialog = () => {
    setIsCreateDialogOpen(false);
    restoreFocus();
  };

  const canCreateWorkspaces = canUserCreateWorkspaces(session);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
        Loading workspaces…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to load your workspaces.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
  }

  const workspaces = workspacesData ?? [];
  const hasWorkspaces = workspaces.length > 0;
  const showEmptyState = !hasWorkspaces;

  const preferredWorkspaceId = session?.user.preferred_workspace_id;
  const fallbackWorkspaceId =
    preferredWorkspaceId && workspaces.some((workspace) => workspace.id === preferredWorkspaceId)
      ? preferredWorkspaceId
      : workspaces[0]?.id;
  const hasRouteWorkspace =
    params.workspaceId && workspaces.some((workspace) => workspace.id === params.workspaceId);
  const activeWorkspace = hasRouteWorkspace
    ? workspaces.find((workspace) => workspace.id === params.workspaceId)
    : fallbackWorkspaceId
    ? workspaces.find((workspace) => workspace.id === fallbackWorkspaceId) ?? workspaces[0]
    : workspaces[0];
  const resolvedWorkspaceId = activeWorkspace?.id ?? undefined;

  useEffect(() => {
    if (!workspaces.length) {
      return;
    }

    if (params.workspaceId) {
      const exists = workspaces.some((workspace) => workspace.id === params.workspaceId);
      if (!exists) {
        navigate("/workspaces", { replace: true });
      }
      return;
    }

    if (resolvedWorkspaceId) {
      navigate(`/workspaces/${resolvedWorkspaceId}`, { replace: true });
    }
  }, [params.workspaceId, workspaces, resolvedWorkspaceId, navigate]);

  const navigationItems = useMemo(() => {
    const permissions = new Set(activeWorkspace?.permissions ?? []);
    return NAVIGATION.filter((item) => !item.requiredPermission || permissions.has(item.requiredPermission));
  }, [activeWorkspace]);

  const railNavigationItems = useMemo(() => {
    if (!resolvedWorkspaceId) {
      return [];
    }

    return navigationItems.map((item) => ({
      id: item.id,
      label: item.label,
      href: resolveWorkspaceNavLink(resolvedWorkspaceId, item.to),
      end: item.end,
    }));
  }, [navigationItems, resolvedWorkspaceId]);

  const currentWorkspaceId = params.workspaceId;

  const handleWorkspaceSelection = (nextWorkspaceId: string) => {
    if (!nextWorkspaceId || nextWorkspaceId === resolvedWorkspaceId) {
      return;
    }

    if (!currentWorkspaceId) {
      navigate(`/workspaces/${nextWorkspaceId}`);
      return;
    }

    const basePath = `/workspaces/${currentWorkspaceId}`;
    if (!location.pathname.startsWith(basePath)) {
      navigate(`/workspaces/${nextWorkspaceId}`);
      return;
    }

    const suffix = location.pathname.slice(basePath.length);
    navigate(
      `/workspaces/${nextWorkspaceId}${suffix}${location.search ?? ""}${location.hash ?? ""}`,
    );
  };

  return (
    <WorkspaceChromeProvider>
      <WorkspaceChrome
        header={
          <WorkspaceTopBar
            session={session}
            workspaces={workspaces}
            activeWorkspaceId={activeWorkspace?.id}
            onSelectWorkspace={handleWorkspaceSelection}
            canCreateWorkspaces={canCreateWorkspaces}
            onCreateWorkspace={openCreateWorkspaceDialog}
          />
        }
        rail={
          <WorkspaceRail
            workspaces={workspaces}
            activeWorkspaceId={activeWorkspace?.id}
            onSelectWorkspace={handleWorkspaceSelection}
            navigationItems={railNavigationItems}
            canCreateWorkspaces={canCreateWorkspaces}
            onCreateWorkspace={openCreateWorkspaceDialog}
          />
        }
      >
        {showEmptyState ? (
          <WorkspaceEmptyState
            canCreateWorkspaces={canCreateWorkspaces}
            onCreateWorkspace={openCreateWorkspaceDialog}
            session={session}
          />
        ) : (
          <>
            <WorkspaceCanvasHeader workspace={activeWorkspace} />
            <WorkspaceCanvasNavigation items={navigationItems} workspaceId={activeWorkspace?.id} />
            <div className="flex-1 overflow-y-auto px-6 py-10 lg:px-8">
              <Outlet context={{ workspace: activeWorkspace } satisfies WorkspaceLayoutContext} />
            </div>
          </>
        )}
      </WorkspaceChrome>
      <CreateWorkspaceDialog
        open={isCreateDialogOpen}
        onClose={closeCreateWorkspaceDialog}
        onCreated={(workspace) => {
          setIsCreateDialogOpen(false);
          navigate(`/workspaces/${workspace.id}`);
          restoreFocus();
        }}
      />
    </WorkspaceChromeProvider>
  );
}

function canUserCreateWorkspaces(session: SessionEnvelope | null): boolean {
  const user = session?.user;
  if (!user || user.is_service_account) {
    return false;
  }

  const permissions = Array.isArray(user.permissions) ? user.permissions : [];
  return globalCan.createWorkspaces(permissions);
}

import { useMemo, type ReactNode } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
  matchPath,
} from "react-router-dom";

import { LoadingState, PageState } from "@/components/layout";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import type { WorkspaceProfile } from "@/types/workspaces";

import { useSettingsWorkspacesListQuery } from "./data";
import {
  OrganizationApiKeysPage,
  OrganizationAuthenticationPage,
  OrganizationGroupsListPage,
  OrganizationGroupCreatePage,
  OrganizationGroupDetailPage,
  OrganizationRolesListPage,
  OrganizationRoleCreatePage,
  OrganizationRoleDetailPage,
  OrganizationRunControlsPage,
  OrganizationUsersListPage,
  OrganizationUserCreatePage,
  OrganizationUserDetailPage,
} from "./pages/organization";
import {
  WorkspaceDangerPage,
  WorkspaceGeneralPage,
  WorkspaceInvitationsListPage,
  WorkspaceInvitationCreatePage,
  WorkspaceInvitationDetailPage,
  WorkspaceListPage,
  WorkspacePrincipalsListPage,
  WorkspacePrincipalCreatePage,
  WorkspacePrincipalDetailPage,
  WorkspaceProcessingPage,
  WorkspaceRolesListPage,
  WorkspaceRoleCreatePage,
  WorkspaceRoleDetailPage,
} from "./pages/workspaces";
import { SettingsHomePage } from "./pages/SettingsHomePage";
import { settingsPaths } from "./routing/contracts";
import { hasRequiredGlobalPermission, normalizePermissionSet } from "./routing/utils";
import { SettingsAccessDenied, SettingsSectionProvider } from "./shared";
import { SettingsShell } from "./shell/SettingsShell";

function hasWorkspacePermission(workspace: WorkspaceProfile, permission: string) {
  return workspace.permissions.some((entry) => entry.toLowerCase() === permission.toLowerCase());
}

function hasWorkspaceAnyPermission(workspace: WorkspaceProfile, permissions: readonly string[]) {
  return permissions.some((permission) => hasWorkspacePermission(workspace, permission));
}

function SettingsNotFoundPage() {
  return (
    <PageState
      variant="error"
      title="Settings page not found"
      description="The requested settings path is not available."
      className="min-h-[340px]"
    />
  );
}

function WorkspaceRouteGate({
  workspaces,
  isLoading,
  requiredPermissions,
  children,
}: {
  readonly workspaces: readonly WorkspaceProfile[];
  readonly isLoading: boolean;
  readonly requiredPermissions?: readonly string[];
  readonly children: (workspace: WorkspaceProfile) => ReactNode;
}) {
  const { workspaceId } = useParams<{ workspaceId: string }>();

  if (isLoading) {
    return <LoadingState title="Loading workspace" className="min-h-[260px]" />;
  }

  const workspace = workspaces.find((entry) => entry.id === workspaceId) ?? null;

  if (!workspace) {
    return (
      <PageState
        variant="error"
        title="Workspace not found"
        description="This workspace is not in your accessible settings scope."
      />
    );
  }

  if (requiredPermissions && requiredPermissions.length > 0) {
    const allowed = hasWorkspaceAnyPermission(workspace, requiredPermissions);
    if (!allowed) {
      return <SettingsAccessDenied returnHref={settingsPaths.workspaces.general(workspace.id)} />;
    }
  }

  return <>{children(workspace)}</>;
}

function OrganizationIndexRedirect({
  globalPermissions,
}: {
  readonly globalPermissions: ReadonlySet<string>;
}) {
  const firstPath = useMemo(() => {
    const routeCandidates = [
      {
        path: settingsPaths.organization.users,
        permissions: ["users.read_all", "users.manage_all"],
      },
      {
        path: settingsPaths.organization.groups,
        permissions: ["groups.read_all", "groups.manage_all"],
      },
      {
        path: settingsPaths.organization.roles,
        permissions: ["roles.read_all", "roles.manage_all"],
      },
      {
        path: settingsPaths.organization.apiKeys,
        permissions: ["api_keys.read_all", "api_keys.manage_all"],
      },
      {
        path: settingsPaths.organization.authentication,
        permissions: ["system.settings.read", "system.settings.manage"],
      },
      {
        path: settingsPaths.organization.runControls,
        permissions: ["system.settings.read", "system.settings.manage"],
      },
    ] as const;

    const match = routeCandidates.find((candidate) =>
      hasRequiredGlobalPermission({ globalAny: candidate.permissions }, globalPermissions),
    );

    return match?.path ?? settingsPaths.home;
  }, [globalPermissions]);

  return <Navigate to={firstPath} replace />;
}

export default function SettingsConsoleApp() {
  const location = useLocation();
  const global = useGlobalPermissions();
  const globalPermissions = normalizePermissionSet(Array.from(global.permissions));

  const workspacesQuery = useSettingsWorkspacesListQuery();
  const workspaces = workspacesQuery.data?.items ?? [];

  const routeWorkspaceId = useMemo(() => {
    const directMatch = matchPath("/settings/workspaces/:workspaceId/*", location.pathname);
    return directMatch?.params.workspaceId ?? null;
  }, [location.pathname]);

  const selectedWorkspace =
    workspaces.find((workspace) => workspace.id === routeWorkspaceId) ??
    workspaces.find((workspace) => workspace.is_default) ??
    workspaces[0] ??
    null;

  const canAccessOrganization = useMemo(
    () =>
      [
        "users.read_all",
        "users.manage_all",
        "groups.read_all",
        "groups.manage_all",
        "roles.read_all",
        "roles.manage_all",
        "api_keys.read_all",
        "api_keys.manage_all",
        "system.settings.read",
        "system.settings.manage",
      ].some((permission) => globalPermissions.has(permission)),
    [globalPermissions],
  );

  return (
    <SettingsSectionProvider>
      <SettingsShell
        globalPermissions={globalPermissions}
        workspaces={workspaces}
        selectedWorkspace={selectedWorkspace}
      >
        <Routes>
        <Route
          index
          element={
            <SettingsHomePage
              canAccessOrganization={canAccessOrganization}
              hasWorkspaceAccess={workspaces.length > 0}
              defaultWorkspaceId={selectedWorkspace?.id ?? null}
            />
          }
        />

        <Route path="organization" element={<OrganizationIndexRedirect globalPermissions={globalPermissions} />} />
        <Route path="organization/users" element={<OrganizationUsersListPage />} />
        <Route path="organization/users/create" element={<OrganizationUserCreatePage />} />
        <Route path="organization/users/:userId" element={<OrganizationUserDetailPage />} />

        <Route path="organization/groups" element={<OrganizationGroupsListPage />} />
        <Route path="organization/groups/create" element={<OrganizationGroupCreatePage />} />
        <Route path="organization/groups/:groupId" element={<OrganizationGroupDetailPage />} />

        <Route path="organization/roles" element={<OrganizationRolesListPage />} />
        <Route path="organization/roles/create" element={<OrganizationRoleCreatePage />} />
        <Route path="organization/roles/:roleId" element={<OrganizationRoleDetailPage />} />

        <Route path="organization/api/keys" element={<OrganizationApiKeysPage />} />
        <Route path="organization/authentication" element={<OrganizationAuthenticationPage />} />
        <Route path="organization/run/controls" element={<OrganizationRunControlsPage />} />

        <Route path="workspaces" element={<WorkspaceListPage workspaces={workspaces} isLoading={workspacesQuery.isLoading} />} />
        <Route path="workspaces/:workspaceId" element={<Navigate to="general" replace />} />

        <Route
          path="workspaces/:workspaceId/general"
          element={
            <WorkspaceRouteGate workspaces={workspaces} isLoading={workspacesQuery.isLoading}>
              {(workspace) => <WorkspaceGeneralPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/processing"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.settings.manage"]}
            >
              {(workspace) => <WorkspaceProcessingPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/principals"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.members.read", "workspace.members.manage"]}
            >
              {(workspace) => <WorkspacePrincipalsListPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/principals/create"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.members.manage"]}
            >
              {(workspace) => <WorkspacePrincipalCreatePage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/principals/:principalType/:principalId"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.members.read", "workspace.members.manage"]}
            >
              {(workspace) => <WorkspacePrincipalDetailPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/roles"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.roles.read", "workspace.roles.manage"]}
            >
              {(workspace) => <WorkspaceRolesListPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/roles/create"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.roles.manage"]}
            >
              {(workspace) => <WorkspaceRoleCreatePage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/roles/:roleId"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.roles.read", "workspace.roles.manage"]}
            >
              {(workspace) => <WorkspaceRoleDetailPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/invitations"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.invitations.read", "workspace.invitations.manage"]}
            >
              {(workspace) => <WorkspaceInvitationsListPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/invitations/create"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.invitations.manage"]}
            >
              {(workspace) => <WorkspaceInvitationCreatePage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/access/invitations/:invitationId"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.invitations.read", "workspace.invitations.manage"]}
            >
              {(workspace) => <WorkspaceInvitationDetailPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route
          path="workspaces/:workspaceId/lifecycle/danger"
          element={
            <WorkspaceRouteGate
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
              requiredPermissions={["workspace.delete", "workspace.settings.manage"]}
            >
              {(workspace) => <WorkspaceDangerPage workspace={workspace} />}
            </WorkspaceRouteGate>
          }
        />

        <Route path="*" element={<SettingsNotFoundPage />} />
        </Routes>
      </SettingsShell>
    </SettingsSectionProvider>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
  matchPath,
} from "react-router-dom";

import { PageState } from "@/components/layout";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useSession } from "@/providers/auth/SessionContext";
import { fetchMfaStatus, type MfaStatusResponse } from "@/api/auth/api";
import { mapUiError } from "@/api/uiErrors";
import { ProfilePage } from "@/pages/Account/pages/ProfilePage";
import { SecurityPage } from "@/pages/Account/pages/SecurityPage";
import { ApiKeysPage } from "@/pages/Account/pages/ApiKeysPage";
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
  WorkspacePrincipalsListPage,
  WorkspacePrincipalCreatePage,
  WorkspacePrincipalDetailPage,
  WorkspaceProcessingPage,
  WorkspaceRolesListPage,
  WorkspaceRoleCreatePage,
  WorkspaceRoleDetailPage,
  WorkspaceListPage,
} from "./pages/workspaces";
import { SettingsHomePage } from "./pages/SettingsHomePage";
import { settingsPaths } from "./routing/contracts";
import { hasRequiredGlobalPermission, normalizePermissionSet } from "./routing/utils";
import { SettingsSectionProvider } from "./shared";
import { SettingsShell } from "./shell/SettingsShell";
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

function WorkspaceSettingsContainer({
  workspaces,
  isLoading,
}: {
  readonly workspaces: readonly WorkspaceProfile[];
  readonly isLoading: boolean;
}) {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const workspace = useMemo(
    () => workspaces.find((w) => w.id === workspaceId),
    [workspaces, workspaceId],
  );

  if (isLoading) {
    return <PageState variant="loading" title="Loading workspace settings" />;
  }

  if (!workspace) {
    return (
      <PageState
        variant="error"
        title="Workspace not found"
        description="The requested workspace settings could not be loaded."
        className="min-h-[340px]"
      />
    );
  }

  return (
    <Routes>
      <Route index element={<Navigate to="general" replace />} />
      <Route path="general" element={<WorkspaceGeneralPage workspace={workspace} />} />
      <Route path="processing" element={<WorkspaceProcessingPage workspace={workspace} />} />
      <Route path="access/principals" element={<WorkspacePrincipalsListPage workspace={workspace} />} />
      <Route path="access/principals/create" element={<WorkspacePrincipalCreatePage workspace={workspace} />} />
      <Route path="access/principals/:principalType/:principalId" element={<WorkspacePrincipalDetailPage workspace={workspace} />} />
      <Route path="access/roles" element={<WorkspaceRolesListPage workspace={workspace} />} />
      <Route path="access/roles/create" element={<WorkspaceRoleCreatePage workspace={workspace} />} />
      <Route path="access/roles/:roleId" element={<WorkspaceRoleDetailPage workspace={workspace} />} />
      <Route path="access/invitations" element={<WorkspaceInvitationsListPage workspace={workspace} />} />
      <Route path="access/invitations/create" element={<WorkspaceInvitationCreatePage workspace={workspace} />} />
      <Route path="access/invitations/:invitationId" element={<WorkspaceInvitationDetailPage workspace={workspace} />} />
      <Route path="lifecycle/danger" element={<WorkspaceDangerPage workspace={workspace} />} />
      <Route path="*" element={<SettingsNotFoundPage />} />
    </Routes>
  );
}

export default function SettingsConsoleApp() {
  const location = useLocation();
  const session = useSession();
  const global = useGlobalPermissions();
  const globalPermissions = normalizePermissionSet(Array.from(global.permissions));

  const [mfaStatus, setMfaStatus] = useState<MfaStatusResponse | null>(null);
  const [isMfaStatusLoading, setIsMfaStatusLoading] = useState(true);
  const [mfaStatusError, setMfaStatusError] = useState<string | null>(null);

  const refreshMfaStatus = useCallback(async () => {
    setMfaStatusError(null);
    try {
      const status = await fetchMfaStatus();
      setMfaStatus(status);
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to read MFA status right now.",
      });
      setMfaStatusError(mapped.message);
    } finally {
      setIsMfaStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMfaStatus();
  }, [refreshMfaStatus]);

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
        <Route
          path="workspaces/:workspaceId/*"
          element={
            <WorkspaceSettingsContainer
              workspaces={workspaces}
              isLoading={workspacesQuery.isLoading}
            />
          }
        />

        <Route
          path="profile"
          element={
            <ProfilePage
              displayName={session.user.display_name}
              email={session.user.email ?? ""}
              createdAt={session.user.created_at}
            />
          }
        />
        <Route
          path="security"
          element={
            <SecurityPage
              mfaStatus={mfaStatus}
              isMfaStatusLoading={isMfaStatusLoading}
              mfaStatusError={mfaStatusError}
              onRefreshMfaStatus={refreshMfaStatus}
            />
          }
        />
        <Route
          path="api-keys"
          element={
            global.canManageApiKeys ? (
              <ApiKeysPage />
            ) : (
              <PageState
                variant="error"
                title="You do not have access"
                description="API key management is restricted to global administrators in this release."
              />
            )
          }
        />

        <Route path="*" element={<SettingsNotFoundPage />} />
        </Routes>
      </SettingsShell>
    </SettingsSectionProvider>
  );
}

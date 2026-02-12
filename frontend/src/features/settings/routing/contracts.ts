export type SettingsScope = "home" | "organization" | "workspaces";

export type SettingsEntityType =
  | "organizationUser"
  | "organizationGroup"
  | "organizationRole"
  | "workspace"
  | "workspacePrincipal"
  | "workspaceRole"
  | "workspaceInvitation";

export interface SettingsRouteContext {
  readonly scope: SettingsScope;
  readonly entityType?: SettingsEntityType;
  readonly entityId?: string | null;
  readonly workspaceId?: string | null;
  readonly section?: string;
}

export interface PermissionRequirement {
  readonly globalAny?: readonly string[];
  readonly workspaceAny?: readonly string[];
}

export interface SettingsNavNode {
  readonly id: string;
  readonly label: string;
  readonly path: string;
  readonly scope: SettingsScope;
  readonly requiredPermissions?: PermissionRequirement;
  readonly children?: readonly SettingsNavNode[];
}

export const settingsPaths = {
  home: "/settings",
  organization: {
    users: "/settings/organization/users",
    usersCreate: "/settings/organization/users/create",
    userDetail: (userId: string) => `/settings/organization/users/${encodeURIComponent(userId)}`,
    groups: "/settings/organization/groups",
    groupsCreate: "/settings/organization/groups/create",
    groupDetail: (groupId: string) => `/settings/organization/groups/${encodeURIComponent(groupId)}`,
    roles: "/settings/organization/roles",
    rolesCreate: "/settings/organization/roles/create",
    roleDetail: (roleId: string) => `/settings/organization/roles/${encodeURIComponent(roleId)}`,
    apiKeys: "/settings/organization/api/keys",
    authentication: "/settings/organization/authentication",
    runControls: "/settings/organization/run/controls",
  },
  workspaces: {
    list: "/settings/workspaces",
    general: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/general`,
    processing: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/processing`,
    principals: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/principals`,
    principalsCreate: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/principals/create`,
    principalDetail: (workspaceId: string, principalType: string, principalId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/principals/${encodeURIComponent(principalType)}/${encodeURIComponent(principalId)}`,
    roles: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/roles`,
    rolesCreate: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/roles/create`,
    roleDetail: (workspaceId: string, roleId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/roles/${encodeURIComponent(roleId)}`,
    invitations: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/invitations`,
    invitationsCreate: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/invitations/create`,
    invitationDetail: (workspaceId: string, invitationId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/access/invitations/${encodeURIComponent(invitationId)}`,
    danger: (workspaceId: string) =>
      `/settings/workspaces/${encodeURIComponent(workspaceId)}/lifecycle/danger`,
  },
} as const;

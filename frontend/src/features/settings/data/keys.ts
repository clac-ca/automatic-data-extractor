export const settingsKeys = {
  all: () => ["settings"] as const,
  organization: () => [...settingsKeys.all(), "organization"] as const,
  organizationUsers: () => [...settingsKeys.organization(), "users"] as const,
  organizationUsersList: (search: string) =>
    [...settingsKeys.organizationUsers(), "list", { search }] as const,
  organizationUserDetail: (userId: string) =>
    [...settingsKeys.organizationUsers(), "detail", userId] as const,
  organizationUserMemberOf: (userId: string) =>
    [...settingsKeys.organizationUsers(), "memberOf", userId] as const,
  organizationUserRoles: (userId: string) =>
    [...settingsKeys.organizationUsers(), "roles", userId] as const,
  organizationUserApiKeys: (userId: string) =>
    [...settingsKeys.organizationUsers(), "apiKeys", userId] as const,

  organizationGroups: () => [...settingsKeys.organization(), "groups"] as const,
  organizationGroupsList: (search: string) =>
    [...settingsKeys.organizationGroups(), "list", { search }] as const,
  organizationGroupMembers: (groupId: string) =>
    [...settingsKeys.organizationGroups(), "members", groupId] as const,
  organizationGroupOwners: (groupId: string) =>
    [...settingsKeys.organizationGroups(), "owners", groupId] as const,

  organizationRoles: () => [...settingsKeys.organization(), "roles"] as const,
  organizationRolesList: () => [...settingsKeys.organizationRoles(), "list"] as const,
  organizationPermissions: (scope: "global" | "workspace") =>
    [...settingsKeys.organizationRoles(), "permissions", scope] as const,

  organizationApiKeys: () => [...settingsKeys.organization(), "apiKeys"] as const,
  organizationApiKeysList: (includeRevoked: boolean) =>
    [...settingsKeys.organizationApiKeys(), "list", { includeRevoked }] as const,

  organizationRuntimeSettings: () => [...settingsKeys.organization(), "runtimeSettings"] as const,
  organizationSsoProviders: () => [...settingsKeys.organization(), "ssoProviders"] as const,
  organizationScimTokens: () => [...settingsKeys.organization(), "scimTokens"] as const,

  workspaces: () => [...settingsKeys.all(), "workspaces"] as const,
  workspacesList: () => [...settingsKeys.workspaces(), "list"] as const,
  workspaceDetail: (workspaceId: string) => [...settingsKeys.workspaces(), "detail", workspaceId] as const,

  workspaceRoles: (workspaceId: string) => [...settingsKeys.workspaceDetail(workspaceId), "roles"] as const,
  workspaceRolePermissions: () => [...settingsKeys.workspaces(), "permissions", "workspace"] as const,

  workspacePrincipals: (workspaceId: string) =>
    [...settingsKeys.workspaceDetail(workspaceId), "principals"] as const,

  workspaceInvitations: (workspaceId: string) =>
    [...settingsKeys.workspaceDetail(workspaceId), "invitations"] as const,

  usersLookup: (search: string) => [...settingsKeys.all(), "usersLookup", { search }] as const,
  groupsLookup: (search: string) => [...settingsKeys.all(), "groupsLookup", { search }] as const,
};

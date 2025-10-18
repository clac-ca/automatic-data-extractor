export const workspacesKeys = {
  all: () => ["workspaces"] as const,
  list: () => [...workspacesKeys.all(), "list"] as const,
  detail: (workspaceId: string) => [...workspacesKeys.all(), "detail", workspaceId] as const,
  members: (workspaceId: string) => [...workspacesKeys.detail(workspaceId), "members"] as const,
  roles: (workspaceId: string) => [...workspacesKeys.detail(workspaceId), "roles"] as const,
  permissions: () => ["permissions"] as const,
};

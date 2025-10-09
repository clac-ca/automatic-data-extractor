export const adminKeys = {
  all: () => ["admin"] as const,
  permissions: () => [...adminKeys.all(), "permissions"] as const,
  globalRoles: () => [...adminKeys.all(), "roles", "global"] as const,
  globalAssignments: (filters?: { principal_id?: string; role_id?: string }) =>
    filters
      ? [...adminKeys.all(), "assignments", "global", filters] as const
      : ([...adminKeys.all(), "assignments", "global"] as const),
  workspaceAssignments: (workspaceId: string, filters?: { principal_id?: string; role_id?: string }) =>
    filters
      ? ([...adminKeys.all(), "assignments", "workspace", workspaceId, filters] as const)
      : ([...adminKeys.all(), "assignments", "workspace", workspaceId] as const),
  users: () => [...adminKeys.all(), "users"] as const,
};

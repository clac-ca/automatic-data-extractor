export const configurationKeys = {
  root: (workspaceId: string) => ["workspaces", workspaceId, "configurations"] as const,
  list: (workspaceId: string, params: { limit?: number; cursor?: string | null } = {}) =>
    [...configurationKeys.root(workspaceId), "list", { ...params }] as const,
  detail: (workspaceId: string, configId: string) =>
    [...configurationKeys.root(workspaceId), "detail", configId] as const,
  files: (workspaceId: string, configId: string) =>
    [...configurationKeys.detail(workspaceId, configId), "files"] as const,
  file: (workspaceId: string, configId: string, path: string) =>
    [...configurationKeys.files(workspaceId, configId), "file", path] as const,
};

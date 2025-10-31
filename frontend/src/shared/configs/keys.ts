export const configsKeys = {
  root: (workspaceId: string) => ["workspaces", workspaceId, "configs"] as const,
  list: (workspaceId: string, statuses?: readonly string[] | null) =>
    [
      ...configsKeys.root(workspaceId),
      "list",
      statuses && statuses.length > 0 ? [...statuses].sort().join(",") : "default",
    ] as const,
  detail: (workspaceId: string, configId: string) =>
    [...configsKeys.root(workspaceId), "detail", configId] as const,
  manifest: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "manifest"] as const,
  files: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "files"] as const,
  file: (workspaceId: string, configId: string, path: string) =>
    [...configsKeys.files(workspaceId, configId), "file", path] as const,
  validation: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "validation"] as const,
  secrets: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "secrets"] as const,
};

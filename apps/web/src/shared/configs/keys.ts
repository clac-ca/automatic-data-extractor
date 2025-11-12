export const configsKeys = {
  root: (workspaceId: string) => ["workspaces", workspaceId, "configs"] as const,
  list: (workspaceId: string, params: { page?: number; pageSize?: number } = {}) =>
    [...configsKeys.root(workspaceId), "list", { ...params }] as const,
  detail: (workspaceId: string, configId: string) =>
    [...configsKeys.root(workspaceId), "detail", configId] as const,
  versions: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "versions"] as const,
  version: (workspaceId: string, configId: string, versionId: string) =>
    [...configsKeys.detail(workspaceId, configId), "version", versionId] as const,
  scripts: (workspaceId: string, configId: string, versionId: string) =>
    [...configsKeys.version(workspaceId, configId, versionId), "scripts"] as const,
  script: (workspaceId: string, configId: string, versionId: string, path: string) =>
    [...configsKeys.scripts(workspaceId, configId, versionId), "script", path] as const,
  manifest: (workspaceId: string, configId: string, versionId: string) =>
    [...configsKeys.version(workspaceId, configId, versionId), "manifest"] as const,
  files: (workspaceId: string, configId: string) =>
    [...configsKeys.detail(workspaceId, configId), "files"] as const,
  file: (workspaceId: string, configId: string, path: string) =>
    [...configsKeys.files(workspaceId, configId), "file", path] as const,
};

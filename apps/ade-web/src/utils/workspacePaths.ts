export const DEFAULT_WORKSPACE_SECTION_PATH = "documents" as const;

export function getDefaultWorkspacePath(workspaceId: string) {
  return `/workspaces/${workspaceId}/${DEFAULT_WORKSPACE_SECTION_PATH}`;
}


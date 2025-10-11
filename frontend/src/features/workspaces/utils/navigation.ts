export interface WorkspaceNavItemConfig {
  id: string;
  label: string;
  to: string;
  end?: boolean;
  requiredPermission?: string;
}

export function resolveWorkspaceNavLink(workspaceId: string, target: string): string {
  if (target === "." || target === "") {
    return `/workspaces/${workspaceId}`;
  }

  const normalized = target.startsWith("/") ? target.slice(1) : target;
  return `/workspaces/${workspaceId}/${normalized}`;
}

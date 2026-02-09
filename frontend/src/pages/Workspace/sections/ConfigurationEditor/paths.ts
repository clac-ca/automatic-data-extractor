export const CONFIGURATIONS_SECTION_SEGMENT = "configurations";

export function buildConfigurationsPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/${CONFIGURATIONS_SECTION_SEGMENT}`;
}

export function buildConfigurationPath(workspaceId: string, configId: string): string {
  return `${buildConfigurationsPath(workspaceId)}/${encodeURIComponent(configId)}`;
}

export function buildConfigurationEditorPath(workspaceId: string, configId: string): string {
  return buildConfigurationPath(workspaceId, configId);
}

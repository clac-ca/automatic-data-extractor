export interface MinimizedWorkbenchState {
  readonly configId: string;
  readonly configName: string;
}

export function getMinimizedWorkbenchStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.minimized`;
}

export function getWorkbenchReturnPathStorageKey(workspaceId: string) {
  return `ade.ui.workspace.${workspaceId}.workbench.returnPath`;
}

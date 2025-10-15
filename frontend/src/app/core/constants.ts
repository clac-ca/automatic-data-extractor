export interface WorkspaceOption {
  id: string;
  name: string;
}

export const DEFAULT_WORKSPACE_ID = 'demo-workspace';

export const DEMO_WORKSPACES: WorkspaceOption[] = [
  { id: 'demo-workspace', name: 'Demo Workspace' },
  { id: 'operations', name: 'Operations' },
  { id: 'analytics', name: 'Analytics' },
];

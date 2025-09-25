export type WorkspaceRole = "member" | "owner";

export interface WorkspaceProfile {
  workspace_id: string;
  name: string;
  slug: string;
  role: WorkspaceRole;
  permissions: string[];
  is_default: boolean;
}

export interface WorkspaceContext {
  workspace: WorkspaceProfile;
}

export interface WorkspaceProfile {
  id: string;
  name: string;
  slug: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
}

export interface WorkspaceSummary {
  workspace_id: string;
  name: string;
  slug: string;
}

export interface WorkspaceCreatePayload {
  name: string;
  slug?: string | null;
  owner_user_id?: string | null;
  settings?: Record<string, unknown> | null;
}

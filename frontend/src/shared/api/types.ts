export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: Record<string, string[]>;
}

export interface SessionUser {
  user_id: string;
  email: string;
  is_active: boolean;
  is_service_account: boolean;
  display_name?: string | null;
  preferred_workspace_id?: string | null;
  roles?: string[];
  permissions?: string[];
  id?: string;
}

export interface SessionEnvelope {
  user: SessionUser;
  expires_at: string;
  refresh_expires_at: string;
}

export interface SessionResponse {
  session: SessionEnvelope | null;
  providers: AuthProvider[];
  force_sso: boolean;
}

export interface AuthProvider {
  id: string;
  label: string;
  icon_url?: string | null;
  start_url: string;
}

export interface SetupStatusResponse {
  requires_setup: boolean;
  completed_at: string | null;
  force_sso?: boolean;
}

export interface CompleteSetupPayload {
  display_name: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface CreateWorkspacePayload {
  name: string;
  slug?: string;
  owner_user_id?: string;
  settings?: Record<string, unknown>;
}

export interface WorkspaceProfile {
  id: string;
  name: string;
  slug: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
}

export interface WorkspaceRoleDefinition {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  scope: "global" | "workspace";
  workspace_id?: string | null;
  permissions: string[];
  is_system: boolean;
  editable: boolean;
}

export interface WorkspaceMemberUser {
  user_id: string;
  email: string;
  is_active: boolean;
  is_service_account: boolean;
  display_name?: string | null;
  roles?: string[];
  permissions?: string[];
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
  user: WorkspaceMemberUser;
}

export interface WorkspaceMemberCreatePayload {
  user_id: string;
  role_ids?: string[];
}

export interface WorkspaceMemberRolesUpdatePayload {
  role_ids: string[];
}

export interface DocumentTypeDetailResponse {
  id: string;
  display_name: string;
  status: string;
  last_run_at: string | null;
  success_rate_7d: number | null;
  pending_jobs: number;
  active_configuration_id: string;
  configuration_summary: ConfigurationSummary;
  alerts?: string[];
}

export interface ConfigurationSummary {
  version: number;
  published_by: string;
  published_at: string;
  draft: boolean;
  description?: string;
  inputs?: Array<{ name: string; type: string; required: boolean }>;
  revision_notes?: string;
}

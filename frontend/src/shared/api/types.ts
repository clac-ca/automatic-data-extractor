export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: Record<string, string[]>;
}

export interface SessionUser {
  id: string;
  display_name: string;
  email: string;
  preferred_workspace_id?: string | null;
  permissions: string[];
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

export interface WorkspaceSummary {
  id: string;
  name: string;
  status: "active" | "paused" | "error";
  document_types: DocumentTypeSummary[];
}

export interface DocumentTypeSummary {
  id: string;
  display_name: string;
  status: "healthy" | "degraded" | "error" | "paused";
  active_configuration_id: string;
  last_run_at: string | null;
  recent_alerts?: string[];
}

export interface WorkspaceListResponse {
  workspaces: WorkspaceSummary[];
}

export interface CreateWorkspacePayload {
  name: string;
  member_emails?: string[];
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

export interface SessionUser {
  user_id: string;
  email: string;
  is_active: boolean;
  is_service_account: boolean;
  display_name?: string | null;
  preferred_workspace_id?: string | null;
  roles?: string[];
  permissions?: string[];
}

export interface SessionEnvelope {
  user: SessionUser;
  expires_at: string;
  refresh_expires_at: string;
  return_to?: string | null;
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

export interface LoginPayload {
  email: string;
  password: string;
}

export interface SetupPayload {
  display_name: string;
  email: string;
  password: string;
}

export interface SetupStatus {
  requires_setup: boolean;
  completed_at: string | null;
  force_sso: boolean;
}

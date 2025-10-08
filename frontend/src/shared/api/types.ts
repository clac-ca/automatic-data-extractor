export interface ProblemDetail {
  type?: string
  title?: string
  status?: number
  detail?: string
  instance?: string
  errors?: Record<string, string[]>
}

export interface UserProfile {
  user_id: string
  email: string
  role: string
  is_active: boolean
  is_service_account: boolean
  preferred_workspace_id?: string | null
}

export interface SessionEnvelope {
  user: UserProfile
  expires_at: string | null
  refresh_expires_at: string | null
}

export interface AuthProvider {
  id: string
  label: string
  start_url: string
  icon_url?: string | null
}

export interface ProviderDiscoveryResponse {
  providers: AuthProvider[]
  force_sso: boolean
}

export interface SetupStatus {
  requires_setup: boolean
  completed_at: string | null
}

export interface SetupRequest {
  email: string
  password: string
  display_name?: string | null
}

export interface LoginRequest {
  email: string
  password: string
}

export interface WorkspaceProfile {
  workspace_id: string
  name: string
  slug: string
  role: string
  permissions: string[]
  is_default: boolean
  document_types?: DocumentTypeSummary[]
}

export interface DocumentTypeSummary {
  id: string
  display_name: string
  status: 'active' | 'paused' | 'draft'
  last_run_at?: string | null
  success_rate_7d?: number | null
  pending_jobs?: number | null
  active_configuration_id?: string | null
  recent_alerts?: DocumentAlertSummary[]
}

export interface DocumentAlertSummary {
  id: string
  title: string
  level: 'info' | 'warning' | 'critical'
  occurred_at: string
}

export interface ConfigurationSummary {
  configuration_id: string
  version: number
  published_by?: string | null
  published_at?: string | null
  description?: string | null
  draft?: boolean
  inputs?: Array<{ name: string; type: string; description?: string | null }>
}

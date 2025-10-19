export interface UserProfile {
  user_id: string;
  email: string;
  is_active: boolean;
  is_service_account: boolean;
  display_name?: string | null;
  preferred_workspace_id?: string | null;
  roles: string[];
  permissions: string[];
}

export interface UserSummary extends UserProfile {
  created_at: string;
  updated_at: string;
}

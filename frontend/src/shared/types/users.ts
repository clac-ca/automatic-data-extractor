export interface UserSummary {
  user_id: string;
  email: string;
  is_active: boolean;
  is_service_account: boolean;
  display_name?: string | null;
  roles: string[];
  permissions: string[];
  preferred_workspace_id?: string | null;
  created_at: string;
  updated_at: string;
}

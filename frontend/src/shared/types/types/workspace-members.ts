import type { UserProfile } from "./users";

export interface WorkspaceMember {
  workspace_membership_id: string;
  workspace_id: string;
  roles: string[];
  permissions: string[];
  is_default: boolean;
  user: UserProfile;
}

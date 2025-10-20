import { get, post } from "@shared/api";
import type { UserProfile, UserSummary } from "@types/users";

export function fetchUsers() {
  return get<UserSummary[]>("/users");
}

export interface InviteUserPayload {
  readonly email: string;
  readonly display_name?: string | null;
}

export function inviteUser(payload: InviteUserPayload) {
  return post<UserProfile>("/users/invitations", payload);
}

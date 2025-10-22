import { get, post } from "@shared/api";
import type { components } from "@openapi";

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

type UserSummary = components["schemas"]["UserSummary"];
type UserProfile = components["schemas"]["UserProfile"];

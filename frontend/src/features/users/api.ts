import { get } from "@shared/api";
import type { UserSummary } from "@types/users";

export function fetchUsers() {
  return get<UserSummary[]>("/users");
}

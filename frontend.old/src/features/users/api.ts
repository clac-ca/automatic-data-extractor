import { get } from "../../shared/api/client";
import type { UserSummary } from "../../shared/types/users";

export function fetchUsers() {
  return get<UserSummary[]>("/users");
}

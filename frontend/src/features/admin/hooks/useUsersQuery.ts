import { useQuery } from "@tanstack/react-query";

import { fetchUsers } from "../api";
import { adminKeys } from "./adminKeys";
import type { UserSummary } from "../../../shared/api/types";

export function useUsersQuery() {
  return useQuery<UserSummary[]>({
    queryKey: adminKeys.users(),
    queryFn: fetchUsers,
    staleTime: 60_000,
  });
}

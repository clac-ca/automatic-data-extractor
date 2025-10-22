import { useQuery } from "@tanstack/react-query";

import { fetchUsers } from "../api";
import type { components } from "@openapi";

export function useUsersQuery(options: { enabled?: boolean } = {}) {
  return useQuery<UserSummary[]>({
    queryKey: ["users", "all"],
    queryFn: fetchUsers,
    enabled: options.enabled ?? true,
    staleTime: 60_000,
    placeholderData: (previous) => previous ?? [],
  });
}

type UserSummary = components["schemas"]["UserSummary"];

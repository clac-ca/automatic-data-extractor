import { useQuery } from "@tanstack/react-query";

import { fetchUsers } from "../api";

export function useUsersQuery(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["users", "all"],
    queryFn: fetchUsers,
    enabled: options.enabled ?? true,
    staleTime: 60_000,
  });
}

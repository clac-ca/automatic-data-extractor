import { useQuery } from "@tanstack/react-query";

import { fetchSetupStatus } from "../api";

export const setupKeys = {
  all: ["setup"] as const,
  status: () => [...setupKeys.all, "status"] as const,
};

export function useSetupStatusQuery() {
  return useQuery({
    queryKey: setupKeys.status(),
    queryFn: fetchSetupStatus,
    staleTime: 30_000,
  });
}

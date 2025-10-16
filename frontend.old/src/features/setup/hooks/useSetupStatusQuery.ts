import { useQuery } from "@tanstack/react-query";

import { fetchSetupStatus } from "../api";

export const setupKeys = {
  status: ["setup", "status"] as const,
};

export function useSetupStatusQuery(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: setupKeys.status,
    queryFn: fetchSetupStatus,
    enabled: options.enabled ?? true,
  });
}

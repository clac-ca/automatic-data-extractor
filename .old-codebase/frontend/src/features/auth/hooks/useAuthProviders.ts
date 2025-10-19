import { useQuery } from "@tanstack/react-query";

import { fetchProviders, sessionKeys } from "../api";

export function useAuthProviders(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: sessionKeys.providers(),
    queryFn: fetchProviders,
    enabled: options.enabled ?? true,
  });
}

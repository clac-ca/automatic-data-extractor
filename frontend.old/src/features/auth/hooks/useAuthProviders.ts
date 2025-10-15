import { useQuery } from "@tanstack/react-query";

import { fetchProviders } from "../api";
import { sessionKeys } from "../sessionKeys";

export function useAuthProviders(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: sessionKeys.providers(),
    queryFn: fetchProviders,
    enabled: options.enabled ?? true,
  });
}

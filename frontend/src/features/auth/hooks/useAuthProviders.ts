import { useQuery } from "@tanstack/react-query";

import { fetchProviders } from "../api/client";
import { sessionKeys } from "../api/keys";

export function useAuthProviders(options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: sessionKeys.providers(),
    queryFn: fetchProviders,
    enabled: options.enabled ?? true,
  });
}

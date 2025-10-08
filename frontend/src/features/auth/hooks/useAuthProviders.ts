import { useQuery } from "@tanstack/react-query";

import { fetchAuthProviders } from "../api";

export const authKeys = {
  all: ["auth"] as const,
  providers: () => [...authKeys.all, "providers"] as const,
};

export function useAuthProvidersQuery() {
  return useQuery({
    queryKey: authKeys.providers(),
    queryFn: fetchAuthProviders,
    staleTime: 60_000,
  });
}

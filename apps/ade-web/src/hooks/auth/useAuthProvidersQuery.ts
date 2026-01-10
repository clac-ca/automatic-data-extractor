import { useQuery } from "@tanstack/react-query";

import { fetchAuthProviders, sessionKeys, type AuthProviderResponse } from "@api/auth/api";

export function useAuthProvidersQuery() {
  return useQuery<AuthProviderResponse>({
    queryKey: sessionKeys.providers(),
    queryFn: ({ signal }) => fetchAuthProviders({ signal }),
    staleTime: 600_000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

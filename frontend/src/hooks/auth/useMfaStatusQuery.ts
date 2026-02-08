import { useQuery } from "@tanstack/react-query";

import { fetchMfaStatus, sessionKeys, type MfaStatusResponse } from "@/api/auth/api";

interface UseMfaStatusQueryOptions {
  readonly enabled?: boolean;
}

export function useMfaStatusQuery(options: UseMfaStatusQueryOptions = {}) {
  return useQuery<MfaStatusResponse>({
    queryKey: [...sessionKeys.root, "mfa-status"],
    queryFn: ({ signal }) => fetchMfaStatus({ signal }),
    enabled: options.enabled ?? true,
    staleTime: 30_000,
    gcTime: 300_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

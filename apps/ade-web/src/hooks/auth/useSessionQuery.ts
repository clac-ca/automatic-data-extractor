import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchSession, sessionKeys, type SessionEnvelope } from "@api/auth/api";

interface UseSessionQueryOptions {
  readonly enabled?: boolean;
}

export function useSessionQuery(options: UseSessionQueryOptions = {}) {
  const queryClient = useQueryClient();

  const query = useQuery<SessionEnvelope | null>({
    queryKey: sessionKeys.detail(),
    queryFn: async ({ signal }) => {
      const session = await fetchSession({ signal });
      if (!session) {
        return null;
      }
      return session;
    },
    enabled: options.enabled ?? true,
    staleTime: 60_000,
    gcTime: 600_000,
    refetchOnWindowFocus: false,
    refetchOnMount: true,
  });

  const session = query.data ?? null;

  useEffect(() => {
    if (!session) {
      queryClient.removeQueries({ queryKey: sessionKeys.providers(), exact: false });
    }
  }, [queryClient, session]);

  return {
    ...query,
    session,
  };
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { fetchSession, sessionKeys } from "../api";
import type { SessionEnvelope, SessionResponse } from "@schema/auth";

interface UseSessionOptions {
  readonly enabled?: boolean;
}

export function useSessionQuery(options: UseSessionOptions = {}) {
  const queryClient = useQueryClient();

  const query = useQuery<SessionResponse>({
    queryKey: sessionKeys.detail(),
    queryFn: fetchSession,
    enabled: options.enabled ?? true,
  });

  const session: SessionEnvelope | null = query.data?.session ?? null;

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

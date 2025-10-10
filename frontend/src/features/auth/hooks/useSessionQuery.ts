import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { fetchSession } from "../api";
import { sessionKeys } from "../sessionKeys";
import type { SessionEnvelope } from "../../../shared/types/auth";

interface UseSessionOptions {
  readonly enabled?: boolean;
}

export function useSessionQuery(options: UseSessionOptions = {}) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: sessionKeys.detail(),
    queryFn: fetchSession,
    enabled: options.enabled ?? true,
  });

  const session = query.data?.session ?? null;

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

export function useSession(): SessionEnvelope | null {
  const { session } = useSessionQuery();
  return session;
}

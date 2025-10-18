import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { fetchSession } from "../api/client";
import { sessionKeys } from "../api/keys";

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

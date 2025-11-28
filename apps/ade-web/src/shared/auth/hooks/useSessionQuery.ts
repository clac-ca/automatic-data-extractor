import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchBootstrap, sessionKeys, type SessionEnvelope } from "../api";
import { SAFE_MODE_QUERY_KEY } from "@shared/system/hooks";
import { WORKSPACE_LIST_DEFAULT_PARAMS, workspacesKeys } from "@features/Workspace/api/workspaces-api";

interface UseSessionQueryOptions {
  readonly enabled?: boolean;
}

export function useSessionQuery(options: UseSessionQueryOptions = {}) {
  const queryClient = useQueryClient();

  const query = useQuery<SessionEnvelope | null>({
    queryKey: sessionKeys.detail(),
    queryFn: async ({ signal }) => {
      const bootstrap = await fetchBootstrap({ signal });
      if (!bootstrap) {
        return null;
      }
      queryClient.setQueryData(workspacesKeys.list(WORKSPACE_LIST_DEFAULT_PARAMS), bootstrap.workspaces);
      queryClient.setQueryData(SAFE_MODE_QUERY_KEY, bootstrap.safe_mode);
      return bootstrap.user;
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

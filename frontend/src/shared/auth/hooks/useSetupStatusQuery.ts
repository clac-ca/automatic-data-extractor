import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchSetupStatus, type SetupStatus } from "@shared/setup/api";
import { sessionKeys } from "../api";

export function useSetupStatusQuery(enabled = true): UseQueryResult<SetupStatus> {
  return useQuery<SetupStatus>({
    queryKey: sessionKeys.setupStatus(),
    queryFn: ({ signal }) => fetchSetupStatus({ signal }),
    enabled,
    staleTime: 300_000,
    refetchOnWindowFocus: false,
  });
}

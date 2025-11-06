import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigs } from "../api";
import { configsKeys } from "../keys";
import type { ConfigRecord } from "../types";

interface UseConfigsQueryOptions {
  readonly workspaceId: string;
  readonly includeDeleted?: boolean;
  readonly enabled?: boolean;
}

export function useConfigsQuery({ workspaceId, includeDeleted = false, enabled = true }: UseConfigsQueryOptions) {
  return useQuery<ConfigRecord[]>({
    queryKey: configsKeys.list(workspaceId, includeDeleted),
    queryFn: ({ signal }) => listConfigs(workspaceId, { includeDeleted, signal }),
    enabled: enabled && workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function useInvalidateConfigs(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.root(workspaceId) });
  };
}

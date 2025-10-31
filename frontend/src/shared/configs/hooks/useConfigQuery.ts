import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getConfig } from "../api";
import { configsKeys } from "../keys";
import type { ConfigRecord } from "../types";

interface UseConfigQueryOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigQuery({ workspaceId, configId, enabled = true }: UseConfigQueryOptions) {
  return useQuery<ConfigRecord | null>({
    queryKey: configsKeys.detail(workspaceId, configId),
    queryFn: ({ signal }) => getConfig(workspaceId, configId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 10_000,
  });
}

export function useInvalidateConfig(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, configId) });
  };
}

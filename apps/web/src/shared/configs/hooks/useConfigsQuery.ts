import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigs, readConfiguration } from "../api";
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

interface UseConfigQueryOptions {
  readonly workspaceId: string;
  readonly configId?: string;
  readonly enabled?: boolean;
}

export function useConfigQuery({ workspaceId, configId, enabled = true }: UseConfigQueryOptions) {
  return useQuery<ConfigRecord | null>({
    queryKey: configsKeys.detail(workspaceId, configId ?? ""),
    queryFn: ({ signal }) => {
      if (!configId) {
        return Promise.resolve(null);
      }
      return readConfiguration(workspaceId, configId, signal);
    },
    enabled: enabled && workspaceId.length > 0 && Boolean(configId),
    staleTime: 10_000,
  });
}

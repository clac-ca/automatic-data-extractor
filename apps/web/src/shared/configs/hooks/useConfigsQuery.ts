import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigs, readConfiguration } from "../api";
import { configsKeys } from "../keys";
import type { ConfigRecord, ConfigurationPage } from "../types";

const CONFIGS_PAGE_SIZE = 100;

interface UseConfigsQueryOptions {
  readonly workspaceId: string;
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
}

export function useConfigsQuery({
  workspaceId,
  enabled = true,
  page = 1,
  pageSize = CONFIGS_PAGE_SIZE,
}: UseConfigsQueryOptions) {
  return useQuery<ConfigurationPage>({
    queryKey: configsKeys.list(workspaceId, { page, pageSize }),
    queryFn: ({ signal }) => listConfigs(workspaceId, { page, pageSize, signal }),
    enabled: enabled && workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
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

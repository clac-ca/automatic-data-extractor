import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigurations, readConfiguration } from "../api";
import { configurationKeys } from "../keys";
import type { ConfigurationRecord, ConfigurationPage } from "../types";

const CONFIGURATIONS_PAGE_SIZE = 100;

interface UseConfigurationsQueryOptions {
  readonly workspaceId: string;
  readonly enabled?: boolean;
  readonly page?: number;
  readonly pageSize?: number;
}

export function useConfigurationsQuery({
  workspaceId,
  enabled = true,
  page = 1,
  pageSize = CONFIGURATIONS_PAGE_SIZE,
}: UseConfigurationsQueryOptions) {
  return useQuery<ConfigurationPage>({
    queryKey: configurationKeys.list(workspaceId, { page, pageSize }),
    queryFn: ({ signal }) => listConfigurations(workspaceId, { page, pageSize, signal }),
    enabled: enabled && workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous,
  });
}

export function useInvalidateConfigurations(workspaceId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) });
  };
}

interface UseConfigurationQueryOptions {
  readonly workspaceId: string;
  readonly configurationId?: string;
  readonly enabled?: boolean;
}

export function useConfigurationQuery({ workspaceId, configurationId, enabled = true }: UseConfigurationQueryOptions) {
  return useQuery<ConfigurationRecord | null>({
    queryKey: configurationKeys.detail(workspaceId, configurationId ?? ""),
    queryFn: ({ signal }) => {
      if (!configurationId) {
        return Promise.resolve(null);
      }
      return readConfiguration(workspaceId, configurationId, signal);
    },
    enabled: enabled && workspaceId.length > 0 && Boolean(configurationId),
    staleTime: 10_000,
  });
}

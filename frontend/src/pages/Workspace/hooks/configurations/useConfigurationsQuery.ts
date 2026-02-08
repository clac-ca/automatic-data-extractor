import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listConfigurations,
  readConfiguration,
} from "@/api/configurations/api";
import { configurationKeys } from "./keys";
import type {
  ConfigurationRecord,
  ConfigurationPage,
} from "@/types/configurations";

const CONFIGURATIONS_PAGE_SIZE = 100;

interface UseConfigurationsQueryOptions {
  readonly workspaceId: string;
  readonly enabled?: boolean;
  readonly limit?: number;
  readonly cursor?: string | null;
}

export function useConfigurationsQuery({
  workspaceId,
  enabled = true,
  limit = CONFIGURATIONS_PAGE_SIZE,
  cursor = null,
}: UseConfigurationsQueryOptions) {
  return useQuery<ConfigurationPage>({
    queryKey: configurationKeys.list(workspaceId, { limit, cursor }),
    queryFn: ({ signal }) => listConfigurations(workspaceId, { limit, cursor, signal }),
    enabled: enabled && workspaceId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous: ConfigurationPage | undefined) => previous,
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
    staleTime: 0,
    refetchOnMount: "always",
  });
}

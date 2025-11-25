import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigurationVersions, readConfigurationVersion } from "../api";
import { configurationKeys } from "../keys";
import type { ConfigurationVersionRecord } from "../types";

interface UseConfigurationVersionsOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigurationVersionsQuery({
  workspaceId,
  configId,
  enabled = true,
}: UseConfigurationVersionsOptions) {
  return useQuery<ConfigurationVersionRecord[]>({
    queryKey: configurationKeys.versions(workspaceId, configId),
    queryFn: ({ signal }) => listConfigurationVersions(workspaceId, configId, { signal }),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    placeholderData: (previous) => previous ?? [],
    staleTime: 15_000,
  });
}

export function useConfigurationVersionQuery(
  workspaceId: string,
  configId: string,
  configurationVersionId: string,
  enabled = true,
) {
  return useQuery<ConfigurationVersionRecord | null>({
    queryKey: configurationKeys.version(workspaceId, configId, configurationVersionId),
    queryFn: ({ signal }) => readConfigurationVersion(workspaceId, configId, configurationVersionId, signal),
    enabled:
      enabled &&
      workspaceId.length > 0 &&
      configId.length > 0 &&
      configurationVersionId.length > 0,
    staleTime: 10_000,
  });
}

export function useInvalidateConfigurationVersions(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configurationKeys.detail(workspaceId, configId) });
  };
}

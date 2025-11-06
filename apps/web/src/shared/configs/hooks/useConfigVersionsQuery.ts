import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listConfigVersions, readConfigVersion } from "../api";
import { configsKeys } from "../keys";
import type { ConfigVersionRecord } from "../types";

interface UseConfigVersionsOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly includeDeleted?: boolean;
  readonly enabled?: boolean;
}

export function useConfigVersionsQuery({
  workspaceId,
  configId,
  includeDeleted = false,
  enabled = true,
}: UseConfigVersionsOptions) {
  return useQuery<ConfigVersionRecord[]>({
    queryKey: configsKeys.versions(workspaceId, configId, includeDeleted),
    queryFn: ({ signal }) => listConfigVersions(workspaceId, configId, { includeDeleted, signal }),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    placeholderData: (previous) => previous ?? [],
    staleTime: 15_000,
  });
}

export function useConfigVersionQuery(workspaceId: string, configId: string, versionId: string, enabled = true) {
  return useQuery<ConfigVersionRecord | null>({
    queryKey: configsKeys.version(workspaceId, configId, versionId),
    queryFn: ({ signal }) => readConfigVersion(workspaceId, configId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0,
    staleTime: 10_000,
  });
}

export function useInvalidateConfigVersions(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, configId) });
  };
}

import { useQuery } from "@tanstack/react-query";

import { fetchConfigurations } from "../api";

export const configurationKeys = {
  all: (workspaceId: string) => ["workspaces", workspaceId, "configurations"] as const,
  list: (workspaceId: string) => [...configurationKeys.all(workspaceId), "list"] as const,
  columns: (workspaceId: string, configurationId: string) =>
    [...configurationKeys.all(workspaceId), configurationId, "columns"] as const,
  scripts: (workspaceId: string, configurationId: string, canonicalKey: string) =>
    [...configurationKeys.all(workspaceId), configurationId, "scripts", canonicalKey] as const,
  scriptVersion: (
    workspaceId: string,
    configurationId: string,
    canonicalKey: string,
    scriptVersionId: string,
  ) =>
    [
      ...configurationKeys.scripts(workspaceId, configurationId, canonicalKey),
      scriptVersionId,
    ] as const,
};

export function useConfigurationsQuery(workspaceId: string) {
  return useQuery({
    queryKey: configurationKeys.list(workspaceId),
    queryFn: ({ signal }) => fetchConfigurations(workspaceId, signal),
    staleTime: 30_000,
  });
}

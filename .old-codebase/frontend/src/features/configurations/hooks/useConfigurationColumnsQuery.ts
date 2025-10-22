import { useQuery } from "@tanstack/react-query";

import { fetchConfigurationColumns } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useConfigurationColumnsQuery(workspaceId: string, configurationId: string) {
  return useQuery({
    queryKey: configurationKeys.columns(workspaceId, configurationId),
    queryFn: ({ signal }) => fetchConfigurationColumns(workspaceId, configurationId, signal),
    enabled: Boolean(configurationId),
    staleTime: 15_000,
  });
}

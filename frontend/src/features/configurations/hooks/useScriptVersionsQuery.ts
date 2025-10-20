import { useQuery } from "@tanstack/react-query";

import { listScriptVersions } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useScriptVersionsQuery(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
) {
  return useQuery({
    queryKey: configurationKeys.scripts(workspaceId, configurationId, canonicalKey),
    queryFn: ({ signal }) => listScriptVersions(workspaceId, configurationId, canonicalKey, signal),
    enabled: Boolean(configurationId && canonicalKey),
    staleTime: 10_000,
  });
}

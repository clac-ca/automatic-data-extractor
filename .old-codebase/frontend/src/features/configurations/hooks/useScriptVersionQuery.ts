import { useQuery } from "@tanstack/react-query";

import { getScriptVersion } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useScriptVersionQuery(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
  scriptVersionId: string | null,
  { includeCode = false }: { includeCode?: boolean } = {},
) {
  return useQuery({
    queryKey: scriptVersionId
      ? configurationKeys.scriptVersion(workspaceId, configurationId, canonicalKey, scriptVersionId)
      : [...configurationKeys.scripts(workspaceId, configurationId, canonicalKey), "detail"],
    queryFn: ({ signal }) =>
      scriptVersionId
        ? getScriptVersion(workspaceId, configurationId, canonicalKey, scriptVersionId, {
            includeCode,
            signal,
          })
        : Promise.resolve(null),
    enabled: Boolean(configurationId && canonicalKey && scriptVersionId),
  });
}

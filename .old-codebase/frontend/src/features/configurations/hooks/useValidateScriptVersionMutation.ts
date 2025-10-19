import { useMutation, useQueryClient } from "@tanstack/react-query";

import { validateScriptVersion } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useValidateScriptVersionMutation(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ scriptVersionId, etag }: { scriptVersionId: string; etag?: string }) =>
      validateScriptVersion(workspaceId, configurationId, canonicalKey, scriptVersionId, etag),
    onSuccess: (script) => {
      queryClient.invalidateQueries({
        queryKey: configurationKeys.scripts(workspaceId, configurationId, canonicalKey),
      });
      queryClient.setQueryData(
        configurationKeys.scriptVersion(
          workspaceId,
          configurationId,
          canonicalKey,
          script.script_version_id,
        ),
        script,
      );
    },
  });
}

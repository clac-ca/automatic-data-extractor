import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createScriptVersion } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useCreateScriptVersionMutation(
  workspaceId: string,
  configurationId: string,
  canonicalKey: string,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: Parameters<typeof createScriptVersion>[3]) =>
      createScriptVersion(workspaceId, configurationId, canonicalKey, payload),
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

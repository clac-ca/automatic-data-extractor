import { useMutation, useQueryClient } from "@tanstack/react-query";

import { activateConfiguration } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useActivateConfigurationMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (configurationId: string) =>
      activateConfiguration(workspaceId, configurationId),
    onSuccess: (_data, configurationId) => {
      queryClient.invalidateQueries({ queryKey: configurationKeys.list(workspaceId) });
      queryClient.invalidateQueries({
        queryKey: configurationKeys.columns(workspaceId, configurationId),
      });
    },
  });
}

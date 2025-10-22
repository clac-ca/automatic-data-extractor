import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createConfiguration } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useCreateConfigurationMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: Parameters<typeof createConfiguration>[1]) =>
      createConfiguration(workspaceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configurationKeys.list(workspaceId) });
    },
  });
}

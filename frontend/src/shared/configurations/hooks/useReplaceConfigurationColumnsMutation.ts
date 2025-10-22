import { useMutation, useQueryClient } from "@tanstack/react-query";

import { replaceConfigurationColumns } from "../api";
import { configurationKeys } from "./useConfigurationsQuery";

export function useReplaceConfigurationColumnsMutation(
  workspaceId: string,
  configurationId: string,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (columns: Parameters<typeof replaceConfigurationColumns>[2]) =>
      replaceConfigurationColumns(workspaceId, configurationId, columns),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: configurationKeys.columns(workspaceId, configurationId),
      });
    },
  });
}

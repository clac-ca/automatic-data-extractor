import { useMutation, useQueryClient } from "@tanstack/react-query";

import { configurationKeys } from "./keys";
import { createConfiguration, type CreateConfigurationPayload } from "@/api/configurations/api";
import type { ConfigurationRecord } from "@/types/configurations";

export function useCreateConfigurationMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<ConfigurationRecord, Error, CreateConfigurationPayload>({
    mutationFn: (payload) => createConfiguration(workspaceId, payload),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) });
    },
  });
}

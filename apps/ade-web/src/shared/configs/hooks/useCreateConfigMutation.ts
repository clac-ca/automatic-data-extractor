import { useMutation, useQueryClient } from "@tanstack/react-query";

import { configsKeys } from "../keys";
import { createConfig, type CreateConfigPayload } from "../api";
import type { ConfigRecord } from "../types";

export function useCreateConfigMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<ConfigRecord, Error, CreateConfigPayload>({
    mutationFn: (payload) => createConfig(workspaceId, payload),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: configsKeys.root(workspaceId) });
    },
  });
}

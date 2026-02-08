import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  archiveConfiguration,
  createConfiguration,
  updateConfiguration,
  type UpdateConfigurationPayload,
} from "@/api/configurations/api";
import { configurationKeys } from "./keys";
import type { ConfigurationRecord } from "@/types/configurations";

export function useArchiveConfigurationMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<ConfigurationRecord, Error, { configurationId: string }>({
    mutationFn: ({ configurationId }) => archiveConfiguration(workspaceId, configurationId),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) });
    },
  });
}

export function useDuplicateConfigurationMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<
    ConfigurationRecord,
    Error,
    { sourceConfigurationId: string; displayName: string }
  >({
    mutationFn: ({ sourceConfigurationId, displayName }) =>
      createConfiguration(workspaceId, {
        displayName,
        source: { type: "clone", configurationId: sourceConfigurationId },
      }),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) });
    },
  });
}

export function useUpdateConfigurationMutation(workspaceId: string, configurationId: string) {
  const queryClient = useQueryClient();
  return useMutation<ConfigurationRecord, Error, UpdateConfigurationPayload>({
    mutationFn: (payload) => updateConfiguration(workspaceId, configurationId, payload),
    async onSuccess() {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) }),
        queryClient.invalidateQueries({
          queryKey: configurationKeys.detail(workspaceId, configurationId),
        }),
      ]);
    },
  });
}

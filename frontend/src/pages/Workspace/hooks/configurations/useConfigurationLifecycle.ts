import { useMutation, useQueryClient } from "@tanstack/react-query";

import { archiveConfiguration, createConfiguration, publishConfiguration } from "@/api/configurations/api";
import { configurationKeys } from "./keys";
import type { ConfigurationRecord } from "@/types/configurations";
import type { RunResource } from "@/types";

export function usePublishConfigurationMutation(workspaceId: string) {
  const queryClient = useQueryClient();

  return useMutation<RunResource, Error, { configurationId: string }>({
    mutationFn: ({ configurationId }) => publishConfiguration(workspaceId, configurationId),
    async onSuccess() {
      await queryClient.invalidateQueries({ queryKey: configurationKeys.root(workspaceId) });
    },
  });
}

export const useMakeActiveConfigurationMutation = usePublishConfigurationMutation;

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

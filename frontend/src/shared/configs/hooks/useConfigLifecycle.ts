import { useMutation, useQueryClient, type UseMutationOptions } from "@tanstack/react-query";

import {
  activateConfig,
  cloneConfig,
  createConfig,
  deleteConfig,
  exportConfig,
  importConfig,
  updateConfig,
  type CloneConfigPayload,
  type CreateConfigPayload,
  type ExportConfigResult,
  type ImportConfigPayload,
  type UpdateConfigPayload,
} from "../api";
import { configsKeys } from "../keys";
import type { ConfigRecord } from "../types";
import { useInvalidateConfigs } from "./useConfigsQuery";

export function useCreateConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<ConfigRecord, Error, CreateConfigPayload>,
) {
  const queryClient = useQueryClient();
  const invalidateConfigs = useInvalidateConfigs(workspaceId);
  return useMutation<ConfigRecord, Error, CreateConfigPayload>({
    mutationFn: (payload) => createConfig(workspaceId, payload),
    ...options,
    onSuccess: async (data, variables, context) => {
      invalidateConfigs();
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, data.config_id) });
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useCloneConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<ConfigRecord, Error, { sourceId: string } & CloneConfigPayload>,
) {
  const queryClient = useQueryClient();
  const invalidateConfigs = useInvalidateConfigs(workspaceId);
  return useMutation<ConfigRecord, Error, { sourceId: string } & CloneConfigPayload>({
    mutationFn: ({ sourceId, ...payload }) => cloneConfig(workspaceId, sourceId, payload),
    ...options,
    onSuccess: async (data, variables, context) => {
      invalidateConfigs();
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, data.config_id) });
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useImportConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<ConfigRecord, Error, ImportConfigPayload>,
) {
  const queryClient = useQueryClient();
  const invalidateConfigs = useInvalidateConfigs(workspaceId);
  return useMutation<ConfigRecord, Error, ImportConfigPayload>({
    mutationFn: (payload) => importConfig(workspaceId, payload),
    ...options,
    onSuccess: async (data, variables, context) => {
      invalidateConfigs();
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, data.config_id) });
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useActivateConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<ConfigRecord, Error, { config: ConfigRecord }>,
) {
  const queryClient = useQueryClient();
  const invalidateConfigs = useInvalidateConfigs(workspaceId);
  return useMutation<ConfigRecord, Error, { config: ConfigRecord }>({
    mutationFn: ({ config }) => activateConfig(workspaceId, config.config_id),
    ...options,
    onSuccess: async (data, variables, context) => {
      invalidateConfigs();
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, data.config_id) });
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useUpdateConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<ConfigRecord, Error, { config: ConfigRecord; payload: UpdateConfigPayload }>,
) {
  const queryClient = useQueryClient();
  const invalidateConfigs = useInvalidateConfigs(workspaceId);
  return useMutation<ConfigRecord, Error, { config: ConfigRecord; payload: UpdateConfigPayload }>({
    mutationFn: ({ config, payload }) => updateConfig(workspaceId, config.config_id, payload),
    ...options,
    onSuccess: async (data, variables, context) => {
      invalidateConfigs();
      queryClient.invalidateQueries({ queryKey: configsKeys.detail(workspaceId, data.config_id) });
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useDeleteConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<void, Error, { config: ConfigRecord }>,
) {
  const queryClient = useQueryClient();
  const invalidateConfigs = useInvalidateConfigs(workspaceId);
  return useMutation<void, Error, { config: ConfigRecord }>({
    mutationFn: ({ config }) => deleteConfig(workspaceId, config.config_id),
    ...options,
    onSuccess: async (data, variables, context) => {
      invalidateConfigs();
      queryClient.removeQueries({ queryKey: configsKeys.detail(workspaceId, variables.config.config_id) });
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

export function useExportConfigMutation(
  workspaceId: string,
  options?: UseMutationOptions<ExportConfigResult, Error, { config: ConfigRecord }>,
) {
  return useMutation<ExportConfigResult, Error, { config: ConfigRecord }>({
    mutationFn: ({ config }) => exportConfig(workspaceId, config.config_id),
    ...options,
    onSuccess: async (data, variables, context) => {
      await options?.onSuccess?.(data, variables, context);
    },
  });
}

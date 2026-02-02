import { useMutation } from "@tanstack/react-query";

import {
  importConfiguration,
  replaceConfigurationFromArchive,
  type ImportConfigurationPayload,
  type ReplaceConfigurationPayload,
} from "@/api/configurations/api";
import type { ConfigurationRecord } from "@/types/configurations";

export function useImportConfigurationMutation(workspaceId: string) {
  return useMutation<ConfigurationRecord, Error, ImportConfigurationPayload>({
    mutationFn: (payload) => importConfiguration(workspaceId, payload),
  });
}

export function useReplaceConfigurationMutation(workspaceId: string, configurationId: string) {
  return useMutation<ConfigurationRecord, Error, ReplaceConfigurationPayload>({
    mutationFn: (payload) => replaceConfigurationFromArchive(workspaceId, configurationId, payload),
  });
}


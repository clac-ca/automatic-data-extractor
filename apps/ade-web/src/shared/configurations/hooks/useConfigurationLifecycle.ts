import { useMutation } from "@tanstack/react-query";

import { activateConfiguration, deactivateConfiguration } from "../api";
import type { ConfigurationRecord } from "../types";

export function useActivateConfigurationMutation(workspaceId: string, configurationId: string) {
  return useMutation<ConfigurationRecord, Error, void>({
    mutationFn: () => activateConfiguration(workspaceId, configurationId),
  });
}

export function useDeactivateConfigurationMutation(workspaceId: string, configurationId: string) {
  return useMutation<ConfigurationRecord, Error, void>({
    mutationFn: () => deactivateConfiguration(workspaceId, configurationId),
  });
}

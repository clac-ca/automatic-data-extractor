import { useMutation } from "@tanstack/react-query";

import { activateConfiguration, deactivateConfiguration } from "../api";
import type { ConfigRecord } from "../types";

export function useActivateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigRecord, Error, void>({
    mutationFn: () => activateConfiguration(workspaceId, configId),
  });
}

export function useDeactivateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigRecord, Error, void>({
    mutationFn: () => deactivateConfiguration(workspaceId, configId),
  });
}

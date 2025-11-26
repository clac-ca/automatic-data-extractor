import { useMutation } from "@tanstack/react-query";

import { validateConfiguration } from "../api";
import type { ConfigurationValidateResponse } from "../types";

export function useValidateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigurationValidateResponse, Error, void>({
    mutationFn: () => validateConfiguration(workspaceId, configId),
  });
}

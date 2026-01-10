import { useMutation } from "@tanstack/react-query";

import { validateConfiguration } from "@api/configurations/api";
import type { ConfigurationValidateResponse } from "@schema/configurations";

export function useValidateConfigurationMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigurationValidateResponse, Error, void>({
    mutationFn: () => validateConfiguration(workspaceId, configId),
  });
}

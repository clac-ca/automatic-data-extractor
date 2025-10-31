import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteSecret, listSecrets, upsertSecret } from "../api";
import { configsKeys } from "../keys";
import type { ConfigSecretInput, ConfigSecretMetadata } from "../types";

interface UseConfigSecretsOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigSecretsQuery({
  workspaceId,
  configId,
  enabled = true,
}: UseConfigSecretsOptions) {
  return useQuery<ConfigSecretMetadata[]>({
    queryKey: configsKeys.secrets(workspaceId, configId),
    queryFn: ({ signal }) => listSecrets(workspaceId, configId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 15_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function useUpsertConfigSecretMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ConfigSecretInput) => upsertSecret(workspaceId, configId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configsKeys.secrets(workspaceId, configId) });
    },
  });
}

export function useDeleteConfigSecretMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteSecret(workspaceId, configId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configsKeys.secrets(workspaceId, configId) });
    },
  });
}

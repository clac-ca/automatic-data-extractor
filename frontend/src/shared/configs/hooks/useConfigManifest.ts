import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { readManifest, validateConfig, writeManifest } from "../api";
import { configsKeys } from "../keys";
import type { ConfigValidationResponse, Manifest, ManifestInput } from "../types";

interface UseConfigManifestOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigManifestQuery({ workspaceId, configId, enabled = true }: UseConfigManifestOptions) {
  return useQuery<Manifest | null>({
    queryKey: configsKeys.manifest(workspaceId, configId),
    queryFn: ({ signal }) => readManifest(workspaceId, configId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 10_000,
  });
}

export function useSaveManifestMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<Manifest, Error, ManifestInput>({
    mutationFn: (manifest) => writeManifest(workspaceId, configId, manifest),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configsKeys.manifest(workspaceId, configId) });
    },
  });
}

export function useValidateConfigMutation(workspaceId: string, configId: string) {
  return useMutation<ConfigValidationResponse, Error>({
    mutationFn: () => validateConfig(workspaceId, configId),
  });
}

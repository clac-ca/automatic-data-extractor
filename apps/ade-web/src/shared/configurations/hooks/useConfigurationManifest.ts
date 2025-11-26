import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { patchManifest, readManifest } from "../api";
import { configurationKeys } from "../keys";
import type { ManifestEnvelope, ManifestEnvelopeWithEtag, ManifestPatchRequest } from "../types";

interface UseConfigurationManifestOptions {
  readonly workspaceId: string;
  readonly configurationId: string;
  readonly versionId: string;
  readonly enabled?: boolean;
}

export function useConfigurationManifestQuery({
  workspaceId,
  configurationId,
  versionId,
  enabled = true,
}: UseConfigurationManifestOptions) {
  return useQuery<ManifestEnvelopeWithEtag>({
    queryKey: configurationKeys.manifest(workspaceId, configurationId, versionId),
    queryFn: ({ signal }) => readManifest(workspaceId, configurationId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configurationId.length > 0 && versionId.length > 0,
    staleTime: 10_000,
  });
}

export function usePatchManifestMutation(
  workspaceId: string,
  configurationId: string,
  versionId: string,
) {
  const queryClient = useQueryClient();
  return useMutation<ManifestEnvelope, Error, { manifest: ManifestPatchRequest; etag?: string | null }>({
    mutationFn: ({ manifest, etag }) => patchManifest(workspaceId, configurationId, versionId, manifest, etag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configurationKeys.manifest(workspaceId, configurationId, versionId) });
    },
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { patchManifest, readManifest } from "../api";
import { configsKeys } from "../keys";
import type { ManifestEnvelope, ManifestEnvelopeWithEtag, ManifestPatchRequest } from "../types";

interface UseConfigManifestOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly versionId: string;
  readonly enabled?: boolean;
}

export function useConfigManifestQuery({ workspaceId, configId, versionId, enabled = true }: UseConfigManifestOptions) {
  return useQuery<ManifestEnvelopeWithEtag>({
    queryKey: configsKeys.manifest(workspaceId, configId, versionId),
    queryFn: ({ signal }) => readManifest(workspaceId, configId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0,
    staleTime: 10_000,
  });
}

export function usePatchManifestMutation(
  workspaceId: string,
  configId: string,
  versionId: string,
) {
  const queryClient = useQueryClient();
  return useMutation<ManifestEnvelope, Error, { manifest: ManifestPatchRequest; etag?: string | null }>({
    mutationFn: ({ manifest, etag }) => patchManifest(workspaceId, configId, versionId, manifest, etag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: configsKeys.manifest(workspaceId, configId, versionId) });
    },
  });
}

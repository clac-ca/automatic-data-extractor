import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listConfigFiles,
  readConfigFile,
  upsertConfigFile,
  type UpsertConfigFilePayload,
} from "../api";
import { configsKeys } from "../keys";
import type { ConfigFileContent, ConfigFileListing, ConfigFileWriteResponse } from "../types";

interface UseConfigFilesQueryOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigFilesQuery({ workspaceId, configId, enabled = true }: UseConfigFilesQueryOptions) {
  return useQuery<ConfigFileListing>({
    queryKey: configsKeys.files(workspaceId, configId),
    queryFn: ({ signal }) => listConfigFiles(workspaceId, configId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 5_000,
  });
}

interface UseConfigFileQueryOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly path?: string | null;
  readonly enabled?: boolean;
}

export function useConfigFileQuery({ workspaceId, configId, path, enabled = true }: UseConfigFileQueryOptions) {
  return useQuery<ConfigFileContent | null>({
    queryKey: configsKeys.file(workspaceId, configId, path ?? ""),
    queryFn: ({ signal }) => {
      if (!path) {
        return Promise.resolve(null);
      }
      return readConfigFile(workspaceId, configId, path, signal);
    },
    enabled: enabled && Boolean(workspaceId) && Boolean(configId) && Boolean(path),
    staleTime: 0,
    gcTime: 60_000,
  });
}

export function useSaveConfigFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<ConfigFileWriteResponse, Error, UpsertConfigFilePayload>({
    mutationFn: (payload) => upsertConfigFile(workspaceId, configId, payload),
    async onSuccess(_, variables) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configsKeys.files(workspaceId, configId) }),
        queryClient.invalidateQueries({ queryKey: configsKeys.file(workspaceId, configId, variables.path) }),
      ]);
    },
  });
}

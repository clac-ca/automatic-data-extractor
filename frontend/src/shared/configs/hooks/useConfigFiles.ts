import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteConfigFile,
  listConfigFiles,
  readConfigFile,
  writeConfigFile,
} from "../api";
import { configsKeys } from "../keys";
import type { FileItem } from "../types";

interface UseConfigFilesOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

interface UseConfigFileOptions extends UseConfigFilesOptions {
  readonly path: string;
}

export function useConfigFilesQuery({
  workspaceId,
  configId,
  enabled = true,
}: UseConfigFilesOptions) {
  return useQuery<FileItem[]>({
    queryKey: configsKeys.files(workspaceId, configId),
    queryFn: ({ signal }) => listConfigFiles(workspaceId, configId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 10_000,
  });
}

export function useConfigFileQuery({
  workspaceId,
  configId,
  path,
  enabled = true,
}: UseConfigFileOptions) {
  return useQuery<string>({
    queryKey: configsKeys.file(workspaceId, configId, path),
    queryFn: ({ signal }) => readConfigFile(workspaceId, configId, path, signal),
    enabled:
      enabled && workspaceId.length > 0 && configId.length > 0 && path.trim().length > 0,
  });
}

export function useSaveConfigFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<FileItem, Error, { path: string; content: string }>({
    mutationFn: ({ path, content }) => writeConfigFile(workspaceId, configId, path, content),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: configsKeys.files(workspaceId, configId) });
      queryClient.invalidateQueries({
        queryKey: configsKeys.file(workspaceId, configId, variables.path),
      });
    },
  });
}

export function useDeleteConfigFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (path) => deleteConfigFile(workspaceId, configId, path),
    onSuccess: (_result, path) => {
      queryClient.invalidateQueries({ queryKey: configsKeys.files(workspaceId, configId) });
      queryClient.removeQueries({ queryKey: configsKeys.file(workspaceId, configId, path) });
    },
  });
}

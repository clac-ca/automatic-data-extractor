import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listConfigurationFiles,
  readConfigurationFileJson,
  renameConfigurationFile,
  upsertConfigurationFile,
  deleteConfigurationFile,
  type ListConfigurationFilesOptions,
  type RenameConfigurationFilePayload,
  type UpsertConfigurationFilePayload,
} from "../api";
import { configurationKeys } from "../keys";
import type { FileListing, FileReadJson, FileRenameResponse, FileWriteResponse } from "../types";

interface UseConfigurationFilesQueryOptions extends Partial<ListConfigurationFilesOptions> {
  readonly workspaceId: string;
  readonly configId: string;
  readonly enabled?: boolean;
}

export function useConfigurationFilesQuery({
  workspaceId,
  configId,
  enabled = true,
  ...options
}: UseConfigurationFilesQueryOptions) {
  const {
    prefix = "",
    depth = "infinity",
    include,
    exclude,
    limit,
    pageToken,
    sort = "path",
    order = "asc",
  } = options;

  return useQuery<FileListing>({
    queryKey: [
      ...configurationKeys.files(workspaceId, configId),
      prefix,
      depth,
      include?.join("|") ?? "",
      exclude?.join("|") ?? "",
      limit ?? "",
      pageToken ?? "",
      sort,
      order,
    ],
    queryFn: ({ signal }) =>
      listConfigurationFiles(workspaceId, configId, {
        prefix,
        depth,
        include,
        exclude,
        limit,
        pageToken,
        sort,
        order,
        signal,
      }),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0,
    staleTime: 5_000,
  });
}

interface UseConfigurationFileQueryOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly path?: string | null;
  readonly enabled?: boolean;
}

export function useConfigurationFileQuery({
  workspaceId,
  configId,
  path,
  enabled = true,
}: UseConfigurationFileQueryOptions) {
  return useQuery<FileReadJson | null>({
    queryKey: configurationKeys.file(workspaceId, configId, path ?? ""),
    queryFn: ({ signal }) => {
      if (!path) {
        return Promise.resolve(null);
      }
      return readConfigurationFileJson(workspaceId, configId, path, signal);
    },
    enabled: enabled && Boolean(workspaceId) && Boolean(configId) && Boolean(path),
    staleTime: 0,
    gcTime: 60_000,
  });
}

export function useSaveConfigurationFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<FileWriteResponse, Error, UpsertConfigurationFilePayload>({
    mutationFn: (payload) => upsertConfigurationFile(workspaceId, configId, payload),
    async onSuccess(_, variables) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationKeys.files(workspaceId, configId) }),
        queryClient.invalidateQueries({ queryKey: configurationKeys.file(workspaceId, configId, variables.path) }),
      ]);
    },
  });
}

export function useRenameConfigurationFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<FileRenameResponse, Error, RenameConfigurationFilePayload>({
    mutationFn: (payload) => renameConfigurationFile(workspaceId, configId, payload),
    async onSuccess(_, variables) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationKeys.files(workspaceId, configId) }),
        queryClient.invalidateQueries({ queryKey: configurationKeys.file(workspaceId, configId, variables.fromPath) }),
        queryClient.invalidateQueries({ queryKey: configurationKeys.file(workspaceId, configId, variables.toPath) }),
      ]);
    },
  });
}

export function useDeleteConfigurationFileMutation(workspaceId: string, configId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { path: string; etag?: string | null }>({
    mutationFn: (payload) => deleteConfigurationFile(workspaceId, configId, payload.path, { etag: payload.etag }),
    async onSuccess(_, variables) {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: configurationKeys.files(workspaceId, configId) }),
        queryClient.invalidateQueries({ queryKey: configurationKeys.file(workspaceId, configId, variables.path) }),
      ]);
    },
  });
}

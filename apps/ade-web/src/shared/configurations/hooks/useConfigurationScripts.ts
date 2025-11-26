import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createScript, deleteScript, listScripts, readScript, updateScript } from "../api";
import { configurationKeys } from "../keys";
import type { ConfigurationScriptContent, ConfigurationScriptSummary } from "../types";

interface UseConfigurationScriptsOptions {
  readonly workspaceId: string;
  readonly configId: string;
  readonly versionId: string;
  readonly enabled?: boolean;
}

export function useConfigurationScriptsQuery({
  workspaceId,
  configId,
  versionId,
  enabled = true,
}: UseConfigurationScriptsOptions) {
  return useQuery<ConfigurationScriptSummary[]>({
    queryKey: configurationKeys.scripts(workspaceId, configId, versionId),
    queryFn: ({ signal }) => listScripts(workspaceId, configId, versionId, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0,
    staleTime: 5_000,
    placeholderData: (previous) => previous ?? [],
  });
}

export function useConfigurationScriptQuery(
  workspaceId: string,
  configId: string,
  versionId: string,
  path: string,
  enabled = true,
) {
  return useQuery<ConfigurationScriptContent | null>({
    queryKey: configurationKeys.script(workspaceId, configId, versionId, path),
    queryFn: ({ signal }) => readScript(workspaceId, configId, versionId, path, signal),
    enabled: enabled && workspaceId.length > 0 && configId.length > 0 && versionId.length > 0 && path.length > 0,
    staleTime: 2_000,
  });
}

export function useCreateScriptMutation(workspaceId: string, configId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation<ConfigurationScriptContent, Error, { path: string; template?: string | null; language?: string | null }>({
    mutationFn: (payload) => createScript(workspaceId, configId, versionId, payload),
    onSuccess: (script) => {
      queryClient.invalidateQueries({ queryKey: configurationKeys.scripts(workspaceId, configId, versionId) });
      queryClient.setQueryData(configurationKeys.script(workspaceId, configId, versionId, script.path), script);
    },
  });
}

export function useUpdateScriptMutation(workspaceId: string, configId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation<ConfigurationScriptContent, Error, { path: string; code: string; etag?: string | null }>({
    mutationFn: ({ path, code, etag }) => updateScript(workspaceId, configId, versionId, path, { code, etag }),
    onSuccess: (script) => {
      queryClient.invalidateQueries({ queryKey: configurationKeys.script(workspaceId, configId, versionId, script.path) });
      queryClient.invalidateQueries({ queryKey: configurationKeys.scripts(workspaceId, configId, versionId) });
    },
  });
}

export function useDeleteScriptMutation(workspaceId: string, configId: string, versionId: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { path: string }>({
    mutationFn: ({ path }) => deleteScript(workspaceId, configId, versionId, path),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: configurationKeys.scripts(workspaceId, configId, versionId) });
      queryClient.removeQueries({ queryKey: configurationKeys.script(workspaceId, configId, versionId, variables.path) });
    },
  });
}

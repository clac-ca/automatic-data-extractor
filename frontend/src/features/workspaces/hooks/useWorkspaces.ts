import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '../../../shared/api/query-keys'
import {
  fetchConfiguration,
  fetchDocumentType,
  fetchWorkspace,
  fetchWorkspaces,
} from '../api'

export function useWorkspacesQuery() {
  return useQuery({
    queryKey: queryKeys.workspaces,
    queryFn: fetchWorkspaces,
    staleTime: 60_000,
  })
}

export function useWorkspaceQuery(workspaceId: string | undefined) {
  return useQuery({
    queryKey: workspaceId ? queryKeys.workspace(workspaceId) : ['workspaces', 'missing'],
    queryFn: () => fetchWorkspace(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  })
}

export function useDocumentTypeQuery(
  workspaceId: string | undefined,
  documentTypeId: string | undefined,
) {
  return useQuery({
    queryKey: documentTypeId
      ? queryKeys.documentType(workspaceId ?? 'unknown', documentTypeId)
      : ['document-types', 'missing'],
    queryFn: () => fetchDocumentType(workspaceId!, documentTypeId!),
    enabled: Boolean(workspaceId && documentTypeId),
    staleTime: 15_000,
  })
}

export function useConfigurationQuery(configurationId: string | undefined) {
  return useQuery({
    queryKey: configurationId
      ? queryKeys.configuration(configurationId)
      : ['configurations', 'missing'],
    queryFn: () => fetchConfiguration(configurationId!),
    enabled: Boolean(configurationId),
    staleTime: 15_000,
  })
}

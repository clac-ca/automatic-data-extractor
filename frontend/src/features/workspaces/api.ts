import { apiClient } from '../../shared/api/client'
import {
  ConfigurationSummary,
  DocumentTypeSummary,
  WorkspaceProfile,
} from '../../shared/api/types'

export function fetchWorkspaces() {
  return apiClient.get<WorkspaceProfile[]>('/workspaces')
}

export function fetchWorkspace(workspaceId: string) {
  return apiClient.get<WorkspaceProfile>(`/workspaces/${workspaceId}`)
}

export function fetchDocumentType(workspaceId: string, documentTypeId: string) {
  return apiClient.get<DocumentTypeSummary>(
    `/workspaces/${workspaceId}/document-types/${documentTypeId}`,
  )
}

export function fetchConfiguration(configurationId: string) {
  return apiClient.get<ConfigurationSummary>(
    `/configurations/${configurationId}`,
  )
}

import { apiClient } from '../../shared/api/client'
import {
  SessionEnvelope,
  SetupRequest,
  SetupStatus,
} from '../../shared/api/types'

export function fetchSetupStatus() {
  return apiClient.get<SetupStatus>('/setup/status')
}

export function submitSetup(payload: SetupRequest) {
  return apiClient.post<SetupRequest, SessionEnvelope>('/setup', payload)
}

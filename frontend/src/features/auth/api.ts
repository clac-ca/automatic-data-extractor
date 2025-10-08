import { apiClient } from '../../shared/api/client'
import type {
  ProviderDiscoveryResponse,
  SessionEnvelope,
  LoginRequest,
} from '../../shared/api/types'

export function fetchSession() {
  return apiClient.get<SessionEnvelope>('/auth/session')
}

export function createSession(payload: LoginRequest) {
  return apiClient.post<LoginRequest, SessionEnvelope>('/auth/session', payload)
}

export function deleteSession() {
  return apiClient.delete<void>('/auth/session')
}

export function refreshSession() {
  return apiClient.post<Record<string, never>, SessionEnvelope>(
    '/auth/session/refresh',
    {},
  )
}

export function fetchAuthProviders() {
  return apiClient.get<ProviderDiscoveryResponse>('/auth/providers')
}

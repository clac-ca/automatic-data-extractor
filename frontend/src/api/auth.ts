import type {
  InitialSetupPayload,
  InitialSetupStatus,
  LoginPayload,
  SessionEnvelope,
  UserProfile,
} from './types'
import { getCookie } from '../utils/cookies'

const CSRF_COOKIE_NAME = 'ade_csrf'

function resolveBaseUrl(): string {
  const rawBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''
  if (!rawBaseUrl) {
    throw new Error('VITE_API_BASE_URL is not defined. Configure it before using the authentication client.')
  }
  return rawBaseUrl.endsWith('/') ? rawBaseUrl.slice(0, -1) : rawBaseUrl
}

function buildUrl(path: string): string {
  return resolveBaseUrl() + path
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  return text ? (JSON.parse(text) as T) : ({} as T)
}

export interface LoginSuccess {
  session: SessionEnvelope
  csrfToken: string | null
}

function isSessionEnvelope(value: unknown): value is SessionEnvelope {
  if (!value || typeof value !== 'object') {
    return false
  }
  const candidate = value as Record<string, unknown>
  return (
    'user' in candidate &&
    typeof candidate.user === 'object' &&
    'expires_at' in candidate &&
    typeof candidate.expires_at === 'string' &&
    'refresh_expires_at' in candidate &&
    typeof candidate.refresh_expires_at === 'string'
  )
}

async function submitSessionRequest(
  path: string,
  payload: unknown,
  fallbackError: string,
): Promise<LoginSuccess> {
  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(payload),
  })

  const data = await readJson<SessionEnvelope | { detail?: string }>(response)

  if (!response.ok) {
    let detail: string | undefined
    if (data && typeof data === 'object' && 'detail' in data) {
      detail = (data as { detail?: string }).detail
    }
    const message = detail?.trim() || fallbackError
    throw Object.assign(new Error(message), { status: response.status })
  }

  if (!isSessionEnvelope(data)) {
    throw new Error('Invalid session response received from the server.')
  }

  const headerToken = response.headers.get('X-CSRF-Token')
  return {
    session: data,
    csrfToken: headerToken ?? resolveCsrfToken(),
  }
}

export async function fetchInitialSetupStatus(): Promise<InitialSetupStatus> {
  const response = await fetch(buildUrl('/auth/initial-setup'), {
    method: 'GET',
    credentials: 'include',
  })

  if (!response.ok) {
    const payload = await readJson<{ detail?: string }>(response)
    const detail = payload.detail || 'Unable to determine the setup status.'
    throw Object.assign(new Error(detail), { status: response.status })
  }

  return readJson<InitialSetupStatus>(response)
}

export async function login(credentials: LoginPayload): Promise<LoginSuccess> {
  return submitSessionRequest(
    '/auth/login',
    credentials,
    'Unable to sign in with the provided credentials.',
  )
}

export async function completeInitialSetup(
  payload: InitialSetupPayload,
): Promise<LoginSuccess> {
  return submitSessionRequest(
    '/auth/initial-setup',
    payload,
    'Unable to complete the initial setup.',
  )
}

export async function fetchProfile(): Promise<UserProfile> {
  const response = await fetch(buildUrl('/auth/me'), {
    method: 'GET',
    credentials: 'include',
  })

  if (!response.ok) {
    const payload = await readJson<{ detail?: string }>(response)
    const detail = payload.detail || 'Unable to load the active session.'
    throw Object.assign(new Error(detail), { status: response.status })
  }

  return readJson<UserProfile>(response)
}

export async function logout(csrfToken: string | null): Promise<void> {
  if (!csrfToken) {
    throw new Error('Missing CSRF token; please sign in again before attempting to sign out.')
  }

  const response = await fetch(buildUrl('/auth/logout'), {
    method: 'POST',
    headers: {
      'X-CSRF-Token': csrfToken,
    },
    credentials: 'include',
  })

  if (!response.ok && response.status !== 204) {
    const payload = await readJson<{ detail?: string }>(response)
    const detail = payload.detail || 'Unable to terminate the current session.'
    throw Object.assign(new Error(detail), { status: response.status })
  }
}

export function resolveCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME)
}

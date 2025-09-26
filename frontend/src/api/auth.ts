import type { LoginPayload, SessionEnvelope, UserProfile } from './types'
import { getCookie } from '../utils/cookies'

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL
if (!rawBaseUrl) {
  throw new Error('VITE_API_BASE_URL is not defined. Set it in your environment before starting the frontend.')
}

const API_BASE_URL = rawBaseUrl.replace(/\/$/, '')
const CSRF_COOKIE_NAME = 'ade_csrf'

function buildUrl(path: string): string {
  return API_BASE_URL + path
}

async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  return text ? (JSON.parse(text) as T) : ({} as T)
}

export interface LoginSuccess {
  session: SessionEnvelope
  csrfToken: string | null
}

export async function login(credentials: LoginPayload): Promise<LoginSuccess> {
  const response = await fetch(buildUrl('/auth/login'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(credentials),
  })

  if (!response.ok) {
    const payload = await readJson<{ detail?: string }>(response)
    const detail = payload.detail || 'Unable to sign in with the provided credentials.'
    throw new Error(detail)
  }

  const session = await readJson<SessionEnvelope>(response)
  const headerToken = response.headers.get('X-CSRF-Token')
  return {
    session,
    csrfToken: headerToken ?? resolveCsrfToken(),
  }
}

export async function fetchProfile(): Promise<UserProfile> {
  const response = await fetch(buildUrl('/auth/me'), {
    method: 'GET',
    credentials: 'include',
  })

  if (!response.ok) {
    const payload = await readJson<{ detail?: string }>(response)
    const detail = payload.detail || 'Unable to load the active session.'
    throw new Error(detail)
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
    throw new Error(detail)
  }
}

export function resolveCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME)
}

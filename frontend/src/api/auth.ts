import type {
  InitialSetupPayload,
  InitialSetupStatus,
  LoginPayload,
  SessionEnvelope,
  UserProfile,
} from './types'
import type { ApiError } from './errors'
import { getCookie } from '../utils/cookies'

const CSRF_COOKIE_NAME = 'ade_csrf'
const API_BASE = '/api'

function buildUrl(path: string): string {
  return `${API_BASE}${path}`
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

interface ProblemDetail {
  message?: string
  lockedUntil?: string
  failedAttempts?: number
  retryAfterSeconds?: number
}

function parseInteger(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value)
  }
  if (typeof value === 'string') {
    const parsed = Number.parseInt(value, 10)
    if (!Number.isNaN(parsed)) {
      return parsed
    }
  }
  return undefined
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) {
    return undefined
  }
  const asSeconds = Number.parseInt(value, 10)
  if (!Number.isNaN(asSeconds)) {
    return Math.max(asSeconds, 0)
  }
  const asDate = Date.parse(value)
  if (!Number.isNaN(asDate)) {
    const delta = Math.ceil((asDate - Date.now()) / 1000)
    return Math.max(delta, 0)
  }
  return undefined
}

function extractProblemDetail(value: unknown): ProblemDetail {
  if (!value || typeof value !== 'object') {
    return {}
  }

  const candidate = value as Record<string, unknown>
  if (!('detail' in candidate)) {
    return {}
  }

  const detail = candidate.detail
  if (typeof detail === 'string') {
    const message = detail.trim()
    return message ? { message } : {}
  }

  if (!detail || typeof detail !== 'object') {
    return {}
  }

  const payload = detail as Record<string, unknown>
  const message = typeof payload.message === 'string' ? payload.message.trim() : undefined
  const lockedUntil =
    typeof payload.lockedUntil === 'string' ? payload.lockedUntil : undefined
  const failedAttempts = parseInteger(payload.failedAttempts)
  const retryAfterSeconds = parseInteger(payload.retryAfterSeconds)

  return {
    message,
    lockedUntil,
    failedAttempts,
    retryAfterSeconds,
  }
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

  const data = await readJson<SessionEnvelope | { detail?: unknown }>(response)

  if (!response.ok) {
    const detail = extractProblemDetail(data)
    const retryAfter = detail.retryAfterSeconds ?? parseRetryAfter(response.headers.get('Retry-After'))
    const message = detail.message?.trim() || fallbackError
    const error = Object.assign(new Error(message), {
      status: response.status,
    }) as ApiError
    if (typeof retryAfter === 'number') {
      error.retryAfterSeconds = retryAfter
    }
    if (detail.lockedUntil) {
      error.lockedUntil = detail.lockedUntil
    }
    if (typeof detail.failedAttempts === 'number') {
      error.failedAttempts = detail.failedAttempts
    }
    throw error
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
    const payload = await readJson<{ detail?: unknown }>(response)
    const detail = extractProblemDetail(payload)
    const message = detail.message?.trim() || 'Unable to determine the setup status.'
    const error = Object.assign(new Error(message), {
      status: response.status,
    }) as ApiError
    if (typeof detail.retryAfterSeconds === 'number') {
      error.retryAfterSeconds = detail.retryAfterSeconds
    }
    if (detail.lockedUntil) {
      error.lockedUntil = detail.lockedUntil
    }
    if (typeof detail.failedAttempts === 'number') {
      error.failedAttempts = detail.failedAttempts
    }
    throw error
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
    const payload = await readJson<{ detail?: unknown }>(response)
    const detail = extractProblemDetail(payload)
    const message = detail.message?.trim() || 'Unable to load the active session.'
    const error = Object.assign(new Error(message), {
      status: response.status,
    }) as ApiError
    if (typeof detail.retryAfterSeconds === 'number') {
      error.retryAfterSeconds = detail.retryAfterSeconds
    }
    if (detail.lockedUntil) {
      error.lockedUntil = detail.lockedUntil
    }
    if (typeof detail.failedAttempts === 'number') {
      error.failedAttempts = detail.failedAttempts
    }
    throw error
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
    const payload = await readJson<{ detail?: unknown }>(response)
    const detail = extractProblemDetail(payload)
    const message = detail.message?.trim() || 'Unable to terminate the current session.'
    const error = Object.assign(new Error(message), {
      status: response.status,
    }) as ApiError
    if (typeof detail.retryAfterSeconds === 'number') {
      error.retryAfterSeconds = detail.retryAfterSeconds
    }
    if (detail.lockedUntil) {
      error.lockedUntil = detail.lockedUntil
    }
    if (typeof detail.failedAttempts === 'number') {
      error.failedAttempts = detail.failedAttempts
    }
    throw error
  }
}

export function resolveCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE_NAME)
}

export type ApiError = Error & {
  status?: number
  lockedUntil?: string
  failedAttempts?: number
  retryAfterSeconds?: number
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof Error
}

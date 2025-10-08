import { ProblemDetail } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export interface RequestOptions extends RequestInit {
  parseJson?: boolean
}

export class ApiError extends Error {
  readonly status: number
  readonly problem?: ProblemDetail
  readonly body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.status = status
    this.body = body
    if (typeof body === 'object' && body !== null) {
      this.problem = body as ProblemDetail
    }
  }
}

async function request<TResponse>(
  path: string,
  init: RequestOptions = {},
): Promise<TResponse> {
  const { parseJson = true, headers, body, ...rest } = init
  const finalHeaders = new Headers(headers)

  if (!finalHeaders.has('Accept')) {
    finalHeaders.set('Accept', 'application/json')
  }

  if (body !== undefined && !finalHeaders.has('Content-Type')) {
    finalHeaders.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    ...rest,
    headers: finalHeaders,
    body,
  })

  const contentType = response.headers.get('content-type') ?? ''
  const contentLength = response.headers.get('content-length')
  const isJsonResponse = /application\/(?:json|problem\+json)/i.test(contentType)
  const shouldParseJson = parseJson && isJsonResponse

  let payload: unknown = null

  if (response.status === 204 || contentLength === '0') {
    payload = null
  } else if (shouldParseJson) {
    try {
      payload = await response.json()
    } catch (error) {
      // Fall back to null so callers can handle unexpected empty bodies.
      payload = null
    }
  } else if (parseJson) {
    const text = await response.text()
    payload = text.length > 0 ? text : null
  }

  if (!response.ok) {
    const message =
      (typeof payload === 'object' && payload && 'title' in payload
        ? String((payload as ProblemDetail).title)
        : response.statusText) || 'Request failed'
    throw new ApiError(message, response.status, payload)
  }

  return (payload ?? undefined) as TResponse
}

function serialiseBody(payload: unknown): string | undefined {
  if (payload === undefined) {
    return undefined
  }

  return JSON.stringify(payload)
}

export const apiClient = {
  get<TResponse>(path: string, init?: RequestOptions) {
    return request<TResponse>(path, { method: 'GET', ...init })
  },
  post<TBody, TResponse>(path: string, payload: TBody, init?: RequestOptions) {
    return request<TResponse>(path, {
      method: 'POST',
      body: serialiseBody(payload),
      ...init,
    })
  },
  put<TBody, TResponse>(path: string, payload: TBody, init?: RequestOptions) {
    return request<TResponse>(path, {
      method: 'PUT',
      body: serialiseBody(payload),
      ...init,
    })
  },
  patch<TBody, TResponse>(
    path: string,
    payload: TBody,
    init?: RequestOptions,
  ) {
    return request<TResponse>(path, {
      method: 'PATCH',
      body: serialiseBody(payload),
      ...init,
    })
  },
  delete<TResponse>(path: string, init?: RequestOptions) {
    return request<TResponse>(path, { method: 'DELETE', ...init })
  },
}

export type ApiClient = typeof apiClient

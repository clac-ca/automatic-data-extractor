import createClient, { type Middleware } from "openapi-fetch";

import { readCsrfToken } from "./csrf";
import { ApiError } from "./errors";
import type { paths } from "@schema";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const AUTH_TOKEN_STORAGE_KEY = "ade.auth.tokens";

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? "";
const baseUrl = rawBaseUrl.endsWith("/api/v1") ? rawBaseUrl.slice(0, -"/api/v1".length) : rawBaseUrl;

export function resolveApiUrl(path: string) {
  if (!path.startsWith("/")) {
    throw new Error("API paths must begin with '/' relative to the server root");
  }
  return baseUrl.length > 0 ? `${baseUrl}${path}` : path;
}

export function buildApiHeaders(method: string, init?: HeadersInit) {
  const headers = new Headers(init ?? {});
  headers.set("X-Requested-With", "fetch");
  if (!headers.has("Authorization")) {
    const token = readStoredAccessToken();
    if (token) {
      headers.set("Authorization", `${token.token_type} ${token.access_token}`);
    }
  }
  const normalizedMethod = method.toUpperCase();
  if (!SAFE_METHODS.has(normalizedMethod)) {
    const token = readCsrfToken();
    if (token && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", token);
    }
  }
  return headers;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const target = resolveApiUrl(path);
  const method = init.method ?? "GET";
  const headers = buildApiHeaders(method, init.headers);
  const response = await fetch(target, {
    credentials: "include",
    ...init,
    headers,
  });
  return response;
}

export const client = createClient<paths>({
  baseUrl: baseUrl.length > 0 ? baseUrl : undefined,
  credentials: "include",
  headers: {
    "X-Requested-With": "fetch",
  },
});

const csrfMiddleware: Middleware = {
  onRequest({ request }) {
    const method = request.method?.toUpperCase() ?? "GET";
    if (!SAFE_METHODS.has(method)) {
      const token = readCsrfToken();
      if (token && !request.headers.has("X-CSRF-Token")) {
        request.headers.set("X-CSRF-Token", token);
      }
    }
    return request;
  },
};

const authMiddleware: Middleware = {
  onRequest({ request }) {
    if (!request.headers.has("Authorization")) {
      const token = readStoredAccessToken();
      if (token) {
        request.headers.set("Authorization", `${token.token_type} ${token.access_token}`);
      }
    }
    return request;
  },
};

const throwOnError: Middleware = {
  async onResponse({ response }) {
    if (response.ok) {
      return response;
    }

    const problem = await tryParseProblem(response);
    const message = problem?.title ?? `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, problem);
  },
};

client.use(csrfMiddleware);
client.use(authMiddleware);
client.use(throwOnError);

function readStoredAccessToken():
  | { access_token: string; token_type: string }
  | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<{
      access_token: string;
      token_type: string;
    }>;
    if (parsed && typeof parsed.access_token === "string") {
      return {
        access_token: parsed.access_token,
        token_type: parsed.token_type ?? "bearer",
      };
    }
  } catch {
    // ignore
  }
  return null;
}

async function tryParseProblem(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined;
  }
  try {
    return await response.clone().json();
  } catch {
    return undefined;
  }
}

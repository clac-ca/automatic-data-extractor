import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { components } from "@schema";

export const sessionKeys = {
  root: ["auth"] as const,
  detail: () => [...sessionKeys.root, "session"] as const,
  providers: () => [...sessionKeys.root, "providers"] as const,
  setupStatus: () => [...sessionKeys.root, "setup-status"] as const,
};

type AuthLoginRequestSchema = components["schemas"]["AuthLoginRequest"];
type AuthTokens = components["schemas"]["SessionTokens"];
type ApiSessionEnvelope = components["schemas"]["SessionEnvelope"];
export type AuthProvider = components["schemas"]["AuthProvider"];
export type AuthProviderResponse = components["schemas"]["AuthProviderListResponse"];
type MeContext = components["schemas"]["MeContext"];
type MeWorkspacePage = MeContext["workspaces"];
type MeWorkspaceSummary = components["schemas"]["MeWorkspaceSummary"];
type MeProfile = components["schemas"]["MeProfile"];
type MeBootstrap = MeContext;

type RequestOptions = {
  readonly signal?: AbortSignal;
};

type LoginPayload = Readonly<Omit<AuthLoginRequestSchema, "email"> & { email: string }>;

type StoredTokens = Readonly<{
  access_token: string;
  token_type: string;
  expires_at: number | null;
  refresh_expires_at: number | null;
}>;

export type SessionUser = Readonly<
  MeProfile & {
    roles: string[];
    permissions: string[];
    preferred_workspace_id: string | null;
  }
>;

type SessionWorkspaces = Omit<MeWorkspacePage, "items"> & { items: MeWorkspaceSummary[] };

export type SessionEnvelope = Readonly<{
  user: SessionUser;
  workspaces: SessionWorkspaces;
  roles: string[];
  permissions: string[];
  expires_at: string | null;
  refresh_expires_at: string | null;
  return_to: string | null;
  state: string | null;
}>;

const TOKEN_STORAGE_KEY = "ade.auth.tokens";
let cachedTokens: StoredTokens | null = readTokensFromStorage();

function readTokensFromStorage(): StoredTokens | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<StoredTokens>;
    if (!parsed || typeof parsed.access_token !== "string") {
      return null;
    }
    return {
      access_token: parsed.access_token,
      token_type: parsed.token_type ?? "bearer",
      expires_at: parsed.expires_at ?? null,
      refresh_expires_at: parsed.refresh_expires_at ?? null,
    };
  } catch {
    return null;
  }
}

function resolveExpiryMs(
  isoTimestamp: string | null | undefined,
  fallbackSeconds: number | null | undefined,
): number | null {
  if (isoTimestamp) {
    const parsed = Date.parse(isoTimestamp);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  if (typeof fallbackSeconds === "number") {
    return Date.now() + fallbackSeconds * 1000;
  }
  return null;
}

function persistTokens(tokens: AuthTokens): StoredTokens {
  const stored: StoredTokens = {
    access_token: tokens.access_token,
    token_type: tokens.token_type ?? "bearer",
    expires_at: resolveExpiryMs(tokens.expires_at, tokens.expires_in),
    refresh_expires_at: resolveExpiryMs(tokens.refresh_expires_at, tokens.refresh_expires_in),
  };

  cachedTokens = stored;

  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(stored));
    } catch {
      // Best-effort persistence; ignore storage failures.
    }
  }

  return stored;
}

export function clearAuthTokens(): void {
  cachedTokens = null;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // ignore
    }
  }
}

function getTokens(): StoredTokens | null {
  return cachedTokens;
}

function authHeader(tokens: StoredTokens | null = cachedTokens): Record<string, string> {
  if (!tokens?.access_token) {
    return {};
  }
  const scheme = tokens.token_type?.trim() || "bearer";
  return {
    Authorization: `${scheme} ${tokens.access_token}`,
  };
}

function toIso(timestamp: number | null): string | null {
  if (!timestamp) {
    return null;
  }
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function preferredWorkspaceId(workspaces: SessionWorkspaces): string | null {
  const preferred = workspaces.items.find((workspace) => workspace.is_default);
  return preferred ? preferred.id : null;
}

function normalizeStringList(values?: string[] | null): string[] {
  if (!Array.isArray(values)) {
    return [];
  }
  return values.filter((value) => typeof value === "string");
}

function normalizeWorkspaces(page: MeWorkspacePage | null | undefined): SessionWorkspaces {
  if (!page) {
    return {
      items: [],
      page: 1,
      page_size: 0,
      total: 0,
      has_next: false,
      has_previous: false,
    };
  }
  return {
    ...page,
    items: page.items ?? [],
  };
}

async function fetchMeBootstrap(tokens: StoredTokens | null, signal?: AbortSignal): Promise<MeBootstrap | null> {
  const path = "/api/v1/me/bootstrap" as const;
  try {
    const { data } = await client.GET(path, {
      signal,
      headers: authHeader(tokens),
      params: {
        query: {
          page: 1,
          page_size: 200,
          include_total: false,
        },
      },
    });
    return data ?? null;
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

function normalizeSessionEnvelope(
  context: MeBootstrap,
  tokens: StoredTokens | null = cachedTokens,
  returnTo: string | null = null,
  state: string | null = null,
): SessionEnvelope {
  const roles = normalizeStringList(context.roles);
  const permissions = normalizeStringList(context.permissions);
  const workspaces = normalizeWorkspaces(context.workspaces);
  return {
    user: {
      ...context.user,
      roles,
      permissions,
      preferred_workspace_id: preferredWorkspaceId(workspaces) ?? null,
    },
    workspaces,
    roles,
    permissions,
    expires_at: toIso(tokens?.expires_at ?? null),
    refresh_expires_at: toIso(tokens?.refresh_expires_at ?? null),
    return_to: returnTo,
    state,
  };
}

export async function establishSessionFromEnvelope(
  envelope: ApiSessionEnvelope,
  options: RequestOptions = {},
): Promise<SessionEnvelope> {
  const stored = persistTokens(envelope.session);
  const context = await fetchMeBootstrap(stored, options.signal);
  if (!context) {
    clearAuthTokens();
    throw new Error("Unable to load session after authentication.");
  }
  return normalizeSessionEnvelope(context, stored, null, null);
}

async function bootstrapSessionFromTokens(
  tokens: AuthTokens,
  signal?: AbortSignal,
): Promise<SessionEnvelope> {
  const stored = persistTokens(tokens);
  const context = await fetchMeBootstrap(stored, signal);
  if (!context) {
    clearAuthTokens();
    throw new Error("Unable to load session after authentication.");
  }
  return normalizeSessionEnvelope(context, stored);
}

export async function fetchAuthProviders(options: RequestOptions = {}): Promise<AuthProviderResponse> {
  try {
    const { data } = await client.GET("/api/v1/auth/providers", {
      signal: options.signal,
    });
    if (!data) {
      return { providers: [], force_sso: false };
    }
    return normalizeAuthProviderResponse(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { providers: [], force_sso: false };
    }
    throw error;
  }
}

export async function fetchSession(options: RequestOptions = {}): Promise<SessionEnvelope | null> {
  const tokens = getTokens();
  const context = await fetchMeBootstrap(tokens, options.signal);

  if (!context) {
    if (tokens) {
      clearAuthTokens();
    }
    return null;
  }

  return normalizeSessionEnvelope(context, tokens);
}

export async function createSession(
  payload: LoginPayload,
  options: RequestOptions = {},
): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session", {
    body: payload,
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected session payload from login response.");
  }

  return establishSessionFromEnvelope(data, options);
}

export async function refreshSession(options: RequestOptions = {}): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session/refresh", {
    body: undefined,
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected session payload from refresh response.");
  }

  return establishSessionFromEnvelope(data, options);
}

export async function completeSsoLogin(params: {
  code: string;
  state: string;
  provider?: string;
  signal?: AbortSignal;
}): Promise<SessionEnvelope> {
  const { code, state, provider = "sso", signal } = params;
  const { data } = await client.GET("/api/v1/auth/sso/{provider}/callback", {
    signal,
    params: {
      path: { provider },
      query: { code, state },
    },
  });

  if (!data) {
    throw new Error("Expected session payload from SSO callback.");
  }

  return establishSessionFromEnvelope(data, { signal });
}

export async function performLogout(options: RequestOptions = {}): Promise<void> {
  try {
    await client.DELETE("/api/v1/auth/session", {
      signal: options.signal,
      body: undefined,
    });
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || (error.status !== 401 && error.status !== 403)) {
      if (import.meta.env.DEV) {
        const reason = error instanceof Error ? error : new Error(String(error));
        console.warn("Failed to terminate session", reason);
      }
    }
  } finally {
    clearAuthTokens();
  }
}

export async function establishSessionFromTokens(
  tokens: AuthTokens,
  signal?: AbortSignal,
): Promise<SessionEnvelope> {
  return bootstrapSessionFromTokens(tokens, signal);
}

function normalizeAuthProviderResponse(data: AuthProviderResponse): AuthProviderResponse {
  return {
    providers: (data.providers ?? []).map(normalizeAuthProvider),
    force_sso: Boolean(data.force_sso),
  };
}

function normalizeAuthProvider(provider: AuthProvider): AuthProvider {
  return {
    ...provider,
    start_url: provider.start_url ?? "",
    icon_url: provider.icon_url ?? null,
  };
}

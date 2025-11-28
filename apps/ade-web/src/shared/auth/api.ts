import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { components } from "@schema";
import type { WorkspaceListPage } from "@features/Workspace/api/workspaces-api";
import type { SafeModeStatus } from "@shared/system/api";

export const sessionKeys = {
  root: ["auth"] as const,
  detail: () => [...sessionKeys.root, "session"] as const,
  providers: () => [...sessionKeys.root, "providers"] as const,
  setupStatus: () => [...sessionKeys.root, "setup-status"] as const,
  bootstrap: () => [...sessionKeys.root, "bootstrap"] as const,
};

export async function fetchSession(options: RequestOptions = {}): Promise<SessionEnvelope | null> {
  try {
    const { data } = await client.GET("/api/v1/auth/session", {
      signal: options.signal,
    });
    return extractSessionEnvelope(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

export async function fetchAuthProviders(options: RequestOptions = {}): Promise<AuthProviderResponse> {
  try {
    const { data } = await client.GET("/api/v1/auth/providers", {
      signal: options.signal,
    });
    return normalizeAuthProviderResponse(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { providers: [], force_sso: false };
    }
    throw error;
  }
}

export async function createSession(payload: LoginPayload, options: RequestOptions = {}): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session", {
    body: payload,
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected session payload.");
  }
  return normalizeSessionEnvelope(data);
}

export async function refreshSession(options: RequestOptions = {}): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session/refresh", {
    signal: options.signal,
  });
  if (!data) {
    throw new Error("Expected session payload.");
  }
  return normalizeSessionEnvelope(data);
}

export function normalizeSessionEnvelope(envelope: SessionEnvelopeWire): SessionEnvelope {
  return {
    ...envelope,
    expires_at: envelope.expires_at ?? null,
    refresh_expires_at: envelope.refresh_expires_at ?? null,
    return_to: envelope.return_to ?? null,
  };
}

export type BootstrapEnvelope = Readonly<{
  user: SessionEnvelope["user"];
  global_roles: string[];
  global_permissions: string[];
  workspaces: WorkspaceListPage;
  safe_mode: SafeModeStatus;
}>;

export async function fetchBootstrap(options: RequestOptions = {}): Promise<BootstrapEnvelope | null> {
  try {
    const { data } = await client.GET("/api/v1/bootstrap", {
      signal: options.signal,
    });
    if (!data) {
      return null;
    }
    return normalizeBootstrapEnvelope(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

function normalizeBootstrapEnvelope(payload: unknown): BootstrapEnvelope {
  const envelope = payload as Partial<BootstrapEnvelope>;
  if (!envelope || !envelope.user) {
    throw new Error("Unexpected bootstrap payload shape returned by the server.");
  }
  return {
    user: normalizeSessionEnvelope({
      user: envelope.user as SessionEnvelope["user"],
      expires_at: null,
      refresh_expires_at: null,
      return_to: null,
    }),
    global_roles: Array.isArray(envelope.global_roles) ? envelope.global_roles.map(String) : [],
    global_permissions: Array.isArray(envelope.global_permissions)
      ? envelope.global_permissions.map(String)
      : [],
    workspaces: envelope.workspaces as WorkspaceListPage,
    safe_mode: (envelope.safe_mode ?? { enabled: false, detail: "" }) as SafeModeStatus,
  };
}

function extractSessionEnvelope(payload: unknown): SessionEnvelope | null {
  if (!payload) {
    return null;
  }

  if (isSessionResponse(payload)) {
    return payload.session ? normalizeSessionEnvelope(payload.session) : null;
  }

  if (isSessionEnvelope(payload)) {
    return normalizeSessionEnvelope(payload);
  }

  throw new Error("Unexpected session payload shape returned by the server.");
}

function isSessionResponse(payload: unknown): payload is SessionResponse {
  if (!payload || typeof payload !== "object") {
    return false;
  }

  const candidate = payload as Partial<SessionResponse>;
  return (
    "session" in candidate &&
    "providers" in candidate &&
    Array.isArray(candidate.providers) &&
    "force_sso" in candidate
  );
}

function isSessionEnvelope(payload: unknown): payload is SessionEnvelopeWire {
  if (!payload || typeof payload !== "object") {
    return false;
  }
  const candidate = payload as Partial<SessionEnvelopeWire>;
  return Boolean(candidate.user);
}

function normalizeAuthProviderResponse(data: unknown): AuthProviderResponse {
  if (!isAuthProviderResponse(data)) {
    return { providers: [], force_sso: false };
  }

  return {
    providers: data.providers.map((provider) => ({
      ...provider,
      icon_url: provider.icon_url ?? null,
    })),
    force_sso: data.force_sso,
  };
}

function isAuthProviderResponse(value: unknown): value is AuthProviderResponse {
  if (!isRecord(value)) {
    return false;
  }
  if (!Array.isArray(value.providers) || typeof value.force_sso !== "boolean") {
    return false;
  }
  return value.providers.every(isAuthProvider);
}

function isAuthProvider(value: unknown): value is AuthProvider {
  if (!isRecord(value)) {
    return false;
  }
  if (
    typeof value.id !== "string" ||
    typeof value.label !== "string" ||
    typeof value.start_url !== "string"
  ) {
    return false;
  }
  return value.icon_url === undefined || value.icon_url === null || typeof value.icon_url === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

interface RequestOptions {
  readonly signal?: AbortSignal;
}

type SessionEnvelopeWire = components["schemas"]["SessionEnvelope"];
type SessionResponse = Readonly<
  {
    session: SessionEnvelopeWire | null;
  } & AuthProviderResponse
>;
type LoginRequestSchema = components["schemas"]["LoginRequest"];

type AuthProvider = components["schemas"]["AuthProvider"];
export type AuthProviderResponse = Readonly<{
  providers: AuthProvider[];
  force_sso: boolean;
}>;
type LoginPayload = Readonly<Omit<LoginRequestSchema, "email"> & { email: string }>;
export type SessionEnvelope = Readonly<
  SessionEnvelopeWire & {
    expires_at: string | null;
    refresh_expires_at: string | null;
    return_to: string | null;
  }
>;

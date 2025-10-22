import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { components } from "@openapi";

export const sessionKeys = {
  root: ["auth"] as const,
  detail: () => [...sessionKeys.root, "session"] as const,
  providers: () => [...sessionKeys.root, "providers"] as const,
  setupStatus: () => [...sessionKeys.root, "setup-status"] as const,
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
    if (!data) {
      return { providers: [], force_sso: false };
    }
    return data as AuthProviderResponse;
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
  };
}

function extractSessionEnvelope(payload: unknown): SessionEnvelope | null {
  if (!payload) {
    return null;
  }

  if (isSessionResponse(payload)) {
    return payload.session ? normalizeSessionEnvelope(payload.session) : null;
  }

  return normalizeSessionEnvelope(payload as SessionEnvelopeWire);
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
  }
>;

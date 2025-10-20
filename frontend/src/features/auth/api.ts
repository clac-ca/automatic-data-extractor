import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { AuthProvider, LoginPayload, SessionEnvelope, SessionResponse } from "@schema/auth";
import type { components } from "@api-types";

export async function fetchSession(): Promise<SessionResponse> {
  try {
    const { data } = await client.GET("/api/v1/auth/session");
    const payload = data ?? null;

    if (isSessionResponse(payload)) {
      return {
        ...payload,
        session: payload.session ? normalizeSessionEnvelope(payload.session) : null,
      } satisfies SessionResponse;
    }

    return {
      session: payload ? normalizeSessionEnvelope(payload) : null,
      providers: [],
      force_sso: false,
    };
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return {
        session: null,
        providers: [],
        force_sso: false,
      };
    }
    throw error;
  }
}

export async function fetchProviders(): Promise<{ providers: AuthProvider[]; force_sso: boolean }> {
  try {
    const { data } = await client.GET("/api/v1/auth/providers");
    if (!data) {
      return { providers: [], force_sso: false };
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { providers: [], force_sso: false };
    }
    throw error;
  }
}

export async function createSession(payload: LoginPayload): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected session payload.");
  }

  return normalizeSessionEnvelope(data);
}

export async function deleteSession(): Promise<void> {
  await client.DELETE("/api/v1/auth/session");
}

export async function refreshSession(): Promise<SessionEnvelope> {
  const { data } = await client.POST("/api/v1/auth/session/refresh");
  if (!data) {
    throw new Error("Expected session payload.");
  }
  return normalizeSessionEnvelope(data);
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

type SessionEnvelopeWire = components["schemas"]["SessionEnvelope"];

function normalizeSessionEnvelope(envelope: SessionEnvelopeWire): SessionEnvelope {
  if (!envelope.expires_at || !envelope.refresh_expires_at) {
    throw new Error("Session envelope missing expiry metadata.");
  }

  return {
    ...envelope,
    expires_at: envelope.expires_at,
    refresh_expires_at: envelope.refresh_expires_at,
  } as SessionEnvelope;
}

export const sessionKeys = {
  all: ["session"] as const,
  detail: () => [...sessionKeys.all, "current"] as const,
  providers: () => [...sessionKeys.all, "providers"] as const,
};

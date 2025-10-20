import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";
import type { AuthProvider, LoginPayload, SessionEnvelope, SessionResponse } from "@schema/auth";

export async function fetchSession() {
  try {
    const { data } = await client.GET("/api/v1/auth/session");
    const envelope = data ?? null;

    if (isSessionResponse(envelope)) {
      return envelope;
    }

    return {
      session: envelope,
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

export async function fetchProviders() {
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

export async function createSession(payload: LoginPayload) {
  const { data } = await client.POST("/api/v1/auth/session", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected session payload.");
  }

  return data;
}

export async function deleteSession() {
  await client.DELETE("/api/v1/auth/session");
}

export async function refreshSession() {
  const { data } = await client.POST("/api/v1/auth/session/refresh");
  if (!data) {
    throw new Error("Expected session payload.");
  }
  return data;
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

export const sessionKeys = {
  all: ["session"] as const,
  detail: () => [...sessionKeys.all, "current"] as const,
  providers: () => [...sessionKeys.all, "providers"] as const,
};

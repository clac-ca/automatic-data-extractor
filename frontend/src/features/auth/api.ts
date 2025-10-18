import { ApiError, del, get, post } from "@shared/api/client";
import type {
  AuthProvider,
  LoginPayload,
  SessionEnvelope,
  SessionResponse,
} from "@shared/types/auth";

export async function fetchSession() {
  try {
    const response = await get<SessionResponse | SessionEnvelope>("/auth/session");

    if (isSessionEnvelope(response)) {
      return {
        session: response,
        providers: [],
        force_sso: false,
      };
    }

    return response;
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
    return await get<{ providers: AuthProvider[]; force_sso: boolean }>("/auth/providers");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { providers: [], force_sso: false };
    }
    throw error;
  }
}

export async function createSession(payload: LoginPayload) {
  return post<SessionEnvelope>("/auth/session", payload);
}

export async function deleteSession() {
  await del("/auth/session", { parseJson: false });
}

export async function refreshSession() {
  return post<SessionEnvelope>("/auth/session/refresh");
}

function isSessionEnvelope(payload: unknown): payload is SessionEnvelope {
  return (
    typeof payload === "object" &&
    payload !== null &&
    "user" in payload &&
    "expires_at" in payload
  );
}

export const sessionKeys = {
  all: ["session"] as const,
  detail: () => [...sessionKeys.all, "current"] as const,
  providers: () => [...sessionKeys.all, "providers"] as const,
};

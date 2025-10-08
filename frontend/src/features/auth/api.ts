import { ApiError, del, get, post } from "../../shared/api/client";
import type {
  AuthProvider,
  CompleteSetupPayload,
  LoginPayload,
  SessionEnvelope,
  SetupStatusResponse,
} from "../../shared/api/types";

export async function fetchSession() {
  try {
    return await get<SessionEnvelope | null>("/auth/session");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }

    throw error;
  }
}

export async function createSession(payload: LoginPayload) {
  return post<SessionEnvelope>("/auth/session", payload);
}

export async function deleteSession() {
  return del<void>("/auth/session", { parseJson: false });
}

export async function refreshSession() {
  return post<SessionEnvelope>("/auth/session/refresh", undefined);
}

export async function fetchAuthProviders() {
  return get<{ providers: AuthProvider[]; force_sso: boolean }>("/auth/providers");
}

export async function fetchSetupStatus() {
  return get<SetupStatusResponse>("/setup/status");
}

export async function completeSetup(payload: CompleteSetupPayload) {
  return post<SessionEnvelope>("/setup", payload);
}

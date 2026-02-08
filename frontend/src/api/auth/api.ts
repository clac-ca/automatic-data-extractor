import { ApiError, buildApiErrorMessage, tryParseProblemDetails } from "@/api/errors";
import { apiFetch, client } from "@/api/client";
import type { components } from "@/types";

export const sessionKeys = {
  root: ["auth"] as const,
  detail: () => [...sessionKeys.root, "session"] as const,
  providers: () => [...sessionKeys.root, "providers"] as const,
  setupStatus: () => [...sessionKeys.root, "setup-status"] as const,
};

type AuthProviderRaw = components["schemas"]["AuthProvider"];
type AuthProviderResponseRaw = components["schemas"]["AuthProviderListResponse"];

export type AuthProvider = Readonly<{
  id: string;
  label: string;
  type: "password" | "oidc";
  startUrl?: string | null;
  iconUrl?: string | null;
}>;

export type AuthProviderResponse = Readonly<{
  providers: AuthProvider[];
  forceSso: boolean;
}>;
type MeContext = components["schemas"]["MeContext"];
type MeWorkspaceSummary = components["schemas"]["MeWorkspaceSummary"];
type MeProfile = components["schemas"]["MeProfile"];

type RequestOptions = {
  readonly signal?: AbortSignal;
};

type LoginPayload = Readonly<{ email: string; password: string }>;
type MfaVerifyPayload = Readonly<{ challengeToken: string; code: string }>;

type LoginApiResponse = Readonly<{
  ok?: boolean;
  mfa_required?: boolean;
  challengeToken?: string;
  challenge_token?: string;
}>;

export type SessionUser = Readonly<
  MeProfile & {
    roles: string[];
    permissions: string[];
    preferred_workspace_id: string | null;
  }
>;

type SessionWorkspaces = MeWorkspaceSummary[];

export type SessionEnvelope = Readonly<{
  user: SessionUser;
  workspaces: SessionWorkspaces;
  roles: string[];
  permissions: string[];
  return_to: string | null;
}>;

export type CreateSessionResult =
  | Readonly<{ kind: "session"; session: SessionEnvelope }>
  | Readonly<{ kind: "mfa_required"; challengeToken: string }>;

export async function fetchAuthProviders(
  options: RequestOptions = {},
): Promise<AuthProviderResponse> {
  try {
    const { data } = await client.GET("/api/v1/auth/providers", {
      signal: options.signal,
    });
    if (!data) {
      return { providers: [], forceSso: false };
    }
    return normalizeAuthProviderResponse(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return { providers: [], forceSso: false };
    }
    throw error;
  }
}

export async function fetchSession(options: RequestOptions = {}): Promise<SessionEnvelope | null> {
  const context = await fetchMeBootstrap(options.signal);
  if (!context) {
    return null;
  }
  return normalizeSessionEnvelope(context, null);
}

export async function createSession(
  payload: LoginPayload,
  options: RequestOptions = {},
): Promise<CreateSessionResult> {
  const login = await submitPasswordLogin(payload, options.signal);
  if (login.mfaRequired) {
    return { kind: "mfa_required", challengeToken: login.challengeToken };
  }
  return { kind: "session", session: await bootstrapSession(options.signal, null) };
}

export async function verifyMfaChallenge(
  payload: MfaVerifyPayload,
  options: RequestOptions = {},
): Promise<SessionEnvelope> {
  await submitMfaChallenge(payload, options.signal);
  return bootstrapSession(options.signal, null);
}

export async function performLogout(options: RequestOptions = {}): Promise<void> {
  try {
    await apiFetch("/api/v1/auth/logout", {
      method: "POST",
      signal: options.signal,
    });
  } catch (error: unknown) {
    if (!(error instanceof ApiError) || (error.status !== 401 && error.status !== 403)) {
      if (import.meta.env.DEV) {
        const reason = error instanceof Error ? error : new Error(String(error));
        console.warn("Failed to terminate session", reason);
      }
    }
  }
}

export async function bootstrapSession(
  signal?: AbortSignal,
  returnTo: string | null = null,
): Promise<SessionEnvelope> {
  const context = await fetchMeBootstrap(signal);
  if (!context) {
    throw new Error("Unable to load session after authentication.");
  }
  return normalizeSessionEnvelope(context, returnTo);
}

async function fetchMeBootstrap(signal?: AbortSignal): Promise<MeContext | null> {
  const path = "/api/v1/me/bootstrap" as const;
  try {
    const { data } = await client.GET(path, { signal });
    return data ?? null;
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      return null;
    }
    throw error;
  }
}

async function submitPasswordLogin(
  payload: LoginPayload,
  signal?: AbortSignal,
): Promise<{ mfaRequired: true; challengeToken: string } | { mfaRequired: false }> {
  const response = await apiFetch("/api/v1/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json()) as LoginApiResponse;
  if (data.mfa_required) {
    const challengeToken = (data.challengeToken ?? data.challenge_token ?? "").trim();
    if (!challengeToken) {
      throw new Error("Missing MFA challenge token from login response.");
    }
    return { mfaRequired: true, challengeToken };
  }
  return { mfaRequired: false };
}

async function submitMfaChallenge(payload: MfaVerifyPayload, signal?: AbortSignal): Promise<void> {
  const response = await apiFetch("/api/v1/auth/mfa/challenge/verify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }
}

function preferredWorkspaceId(workspaces: SessionWorkspaces): string | null {
  const preferred = workspaces.find((workspace) => workspace.is_default);
  return preferred ? preferred.id : null;
}

function normalizeStringList(values?: string[] | null): string[] {
  if (!Array.isArray(values)) {
    return [];
  }
  return values.filter((value) => typeof value === "string");
}

function normalizeWorkspaces(workspaces: MeContext["workspaces"] | null | undefined): SessionWorkspaces {
  if (!Array.isArray(workspaces)) {
    return [];
  }
  return workspaces;
}

function normalizeSessionEnvelope(
  context: MeContext,
  returnTo: string | null = null,
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
    return_to: returnTo,
  };
}

function normalizeAuthProviderResponse(data: AuthProviderResponseRaw): AuthProviderResponse {
  return {
    providers: (data.providers ?? []).map(normalizeAuthProvider),
    forceSso: Boolean(data.force_sso),
  };
}

function normalizeAuthProvider(provider: AuthProviderRaw): AuthProvider {
  return {
    id: provider.id,
    label: provider.label,
    type: provider.type,
    startUrl: provider.start_url ?? "",
    iconUrl: provider.icon_url ?? null,
  };
}

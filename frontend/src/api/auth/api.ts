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
type MfaEnrollStartResponseRaw = components["schemas"]["AuthMfaEnrollStartResponse"];
type MfaEnrollConfirmResponseRaw = components["schemas"]["AuthMfaEnrollConfirmResponse"];
type MfaStatusResponseRaw = components["schemas"]["AuthMfaStatusResponse"];

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
  passwordResetEnabled: boolean;
}>;
type MeContext = components["schemas"]["MeContext"];
type MeWorkspaceSummary = components["schemas"]["MeWorkspaceSummary"];
type MeProfile = components["schemas"]["MeProfile"];

type RequestOptions = {
  readonly signal?: AbortSignal;
};

type LoginPayload = Readonly<{ email: string; password: string }>;
type MfaVerifyPayload = Readonly<{ challengeToken: string; code: string }>;
export type PasswordForgotPayload = Readonly<{ email: string }>;
export type PasswordResetPayload = Readonly<{ token: string; newPassword: string }>;
type MfaCodePayload = Readonly<{ code: string }>;

type LoginApiResponse = Readonly<{
  ok?: boolean;
  mfa_required?: boolean;
  challengeToken?: string;
  challenge_token?: string;
  mfaSetupRecommended?: boolean;
  mfa_setup_recommended?: boolean;
  mfaSetupRequired?: boolean;
  mfa_setup_required?: boolean;
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

export type MfaEnrollStartResponse = Readonly<{
  otpauthUri: string;
  issuer: string;
  accountName: string;
}>;

export type MfaEnrollConfirmResponse = Readonly<{
  recoveryCodes: string[];
}>;

export type MfaStatusResponse = Readonly<{
  enabled: boolean;
  enrolledAt: string | null;
  recoveryCodesRemaining: number | null;
  onboardingRecommended: boolean;
  onboardingRequired: boolean;
  skipAllowed: boolean;
}>;

export type CreateSessionResult =
  | Readonly<{
      kind: "session";
      session: SessionEnvelope;
      mfaSetupRecommended: boolean;
      mfaSetupRequired: boolean;
    }>
  | Readonly<{ kind: "mfa_required"; challengeToken: string }>;

export async function fetchAuthProviders(
  options: RequestOptions = {},
): Promise<AuthProviderResponse> {
  try {
    const { data } = await client.GET("/api/v1/auth/providers", {
      signal: options.signal,
    });
    if (!data) {
      return {
        providers: [],
        forceSso: false,
        passwordResetEnabled: false,
      };
    }
    return normalizeAuthProviderResponse(data);
  } catch (error: unknown) {
    if (error instanceof ApiError && error.status === 404) {
      return {
        providers: [],
        forceSso: false,
        passwordResetEnabled: false,
      };
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
  return {
    kind: "session",
    session: await bootstrapSession(options.signal, null),
    mfaSetupRecommended: login.mfaSetupRecommended,
    mfaSetupRequired: login.mfaSetupRequired,
  };
}

export async function verifyMfaChallenge(
  payload: MfaVerifyPayload,
  options: RequestOptions = {},
): Promise<SessionEnvelope> {
  await submitMfaChallenge(payload, options.signal);
  return bootstrapSession(options.signal, null);
}

export async function requestPasswordReset(
  payload: PasswordForgotPayload,
  options: RequestOptions = {},
): Promise<void> {
  await submitPasswordForgot(payload, options.signal);
}

export async function completePasswordReset(
  payload: PasswordResetPayload,
  options: RequestOptions = {},
): Promise<void> {
  await submitPasswordReset(payload, options.signal);
}

export async function startMfaEnrollment(
  options: RequestOptions = {},
): Promise<MfaEnrollStartResponse> {
  const response = await apiFetch("/api/v1/auth/mfa/totp/enroll/start", {
    method: "POST",
    signal: options.signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json()) as Partial<MfaEnrollStartResponseRaw>;
  const otpauthUri = normalizeRequiredField(data.otpauthUri, "MFA enrollment uri");
  const issuer = normalizeRequiredField(data.issuer, "MFA enrollment issuer");
  const accountName = normalizeRequiredField(data.accountName, "MFA enrollment account name");
  return { otpauthUri, issuer, accountName };
}

export async function confirmMfaEnrollment(
  payload: MfaCodePayload,
  options: RequestOptions = {},
): Promise<MfaEnrollConfirmResponse> {
  const response = await apiFetch("/api/v1/auth/mfa/totp/enroll/confirm", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json()) as Partial<MfaEnrollConfirmResponseRaw>;
  const recoveryCodes = normalizeTrimmedStringList(data.recoveryCodes);
  if (recoveryCodes.length === 0) {
    throw new Error("Missing MFA recovery codes from enrollment response.");
  }
  return { recoveryCodes };
}

export async function fetchMfaStatus(options: RequestOptions = {}): Promise<MfaStatusResponse> {
  const response = await apiFetch("/api/v1/auth/mfa/totp", {
    method: "GET",
    signal: options.signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json()) as Partial<MfaStatusResponseRaw>;
  return {
    enabled: Boolean(data.enabled),
    enrolledAt: normalizeOptionalField(data.enrolledAt),
    recoveryCodesRemaining:
      typeof data.recoveryCodesRemaining === "number" && Number.isFinite(data.recoveryCodesRemaining)
        ? Math.max(0, Math.floor(data.recoveryCodesRemaining))
        : null,
    onboardingRecommended: Boolean(data.onboardingRecommended),
    onboardingRequired: Boolean(data.onboardingRequired),
    skipAllowed: Boolean(data.skipAllowed),
  };
}

export async function regenerateMfaRecoveryCodes(
  payload: MfaCodePayload,
  options: RequestOptions = {},
): Promise<MfaEnrollConfirmResponse> {
  const response = await apiFetch("/api/v1/auth/mfa/totp/recovery/regenerate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }

  const data = (await response.json()) as Partial<MfaEnrollConfirmResponseRaw>;
  const recoveryCodes = normalizeTrimmedStringList(data.recoveryCodes);
  if (recoveryCodes.length === 0) {
    throw new Error("Missing MFA recovery codes from regeneration response.");
  }
  return { recoveryCodes };
}

export async function disableMfa(options: RequestOptions = {}): Promise<void> {
  const response = await apiFetch("/api/v1/auth/mfa/totp", {
    method: "DELETE",
    signal: options.signal,
  });

  if (!response.ok) {
    const problem = await tryParseProblemDetails(response);
    const message = buildApiErrorMessage(problem, response.status);
    throw new ApiError(message, response.status, problem);
  }
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
): Promise<
  | { mfaRequired: true; challengeToken: string }
  | {
      mfaRequired: false;
      mfaSetupRecommended: boolean;
      mfaSetupRequired: boolean;
    }
> {
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
  return {
    mfaRequired: false,
    mfaSetupRecommended: Boolean(
      data.mfaSetupRecommended ?? data.mfa_setup_recommended ?? false,
    ),
    mfaSetupRequired: Boolean(data.mfaSetupRequired ?? data.mfa_setup_required ?? false),
  };
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

async function submitPasswordForgot(
  payload: PasswordForgotPayload,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch("/api/v1/auth/password/forgot", {
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

async function submitPasswordReset(
  payload: PasswordResetPayload,
  signal?: AbortSignal,
): Promise<void> {
  const response = await apiFetch("/api/v1/auth/password/reset", {
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

function normalizeTrimmedStringList(values?: string[] | null): string[] {
  return normalizeStringList(values)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

function normalizeRequiredField(value: unknown, fieldName: string): string {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) {
    throw new Error(`Missing ${fieldName} from API response.`);
  }
  return text;
}

function normalizeOptionalField(value: unknown): string | null {
  const text = typeof value === "string" ? value.trim() : "";
  return text.length > 0 ? text : null;
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
  const raw = data as AuthProviderResponseRaw & {
    password_reset_enabled?: boolean;
  };
  const forceSso = Boolean(raw.force_sso);
  const passwordResetEnabled =
    typeof raw.password_reset_enabled === "boolean" ? raw.password_reset_enabled : !forceSso;

  return {
    providers: (raw.providers ?? []).map(normalizeAuthProvider),
    forceSso,
    passwordResetEnabled,
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

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockClient = {
  POST: vi.fn(),
  GET: vi.fn(),
};

const mockApiFetch = vi.fn();

vi.mock("@/api/client", () => ({
  client: mockClient,
  apiFetch: mockApiFetch,
}));

const meBootstrap = {
  user: {
    id: "user-1",
    email: "user@example.com",
    display_name: "User",
    is_service_account: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  workspaces: [],
  roles: [],
  permissions: [],
};

beforeEach(() => {
  mockClient.POST.mockReset();
  mockClient.GET.mockReset();
  mockApiFetch.mockReset();
  mockClient.POST.mockResolvedValue({ data: null });
  mockClient.GET.mockResolvedValue({ data: meBootstrap });
  mockApiFetch.mockResolvedValue(new Response(JSON.stringify({ ok: true, mfa_required: false }), { status: 200 }));
});

afterEach(() => {
  vi.resetModules();
});

describe("auth api", () => {
  it("creates a cookie session and bootstraps profile data", async () => {
    const { createSession } = await import("../api");

    const result = await createSession({ email: "user@example.com", password: "pass" });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "user@example.com", password: "pass" }),
      }),
    );

    expect(mockClient.GET).toHaveBeenCalledWith("/api/v1/me/bootstrap", { signal: undefined });
    expect(result.kind).toBe("session");
    if (result.kind === "session") {
      expect(result.session.user.email).toBe("user@example.com");
      expect(result.mfaSetupRecommended).toBe(false);
      expect(result.mfaSetupRequired).toBe(false);
    }
  });

  it("returns setup guidance flags when login indicates onboarding", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          ok: true,
          mfa_required: false,
          mfaSetupRecommended: true,
          mfaSetupRequired: false,
        }),
        { status: 200 },
      ),
    );

    const { createSession } = await import("../api");
    const result = await createSession({ email: "user@example.com", password: "pass" });

    expect(result.kind).toBe("session");
    if (result.kind === "session") {
      expect(result.mfaSetupRecommended).toBe(true);
      expect(result.mfaSetupRequired).toBe(false);
    }
  });

  it("returns challenge token when MFA is required", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ ok: true, mfa_required: true, challengeToken: "challenge-123" }),
        { status: 200 },
      ),
    );

    const { createSession } = await import("../api");
    const result = await createSession({ email: "user@example.com", password: "pass" });

    expect(result).toEqual({
      kind: "mfa_required",
      challengeToken: "challenge-123",
    });
    expect(mockClient.GET).not.toHaveBeenCalled();
  });

  it("logs out using the auth logout route", async () => {
    const { performLogout } = await import("../api");

    await performLogout();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/logout",
      expect.objectContaining({ method: "POST", signal: undefined }),
    );
  });

  it("requests password reset using the forgot endpoint", async () => {
    mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 202 }));

    const { requestPasswordReset } = await import("../api");
    await requestPasswordReset({ email: "user@example.com" });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/password/forgot",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "user@example.com" }),
      }),
    );
  });

  it("resets password using the reset endpoint", async () => {
    mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    const { completePasswordReset } = await import("../api");
    await completePasswordReset({
      token: "reset-token",
      newPassword: "averysecurepassword",
    });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/password/reset",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          token: "reset-token",
          newPassword: "averysecurepassword",
        }),
      }),
    );
  });

  it("normalizes auth providers including password reset availability", async () => {
    mockClient.GET.mockResolvedValueOnce({
      data: {
        providers: [],
        force_sso: true,
        password_reset_enabled: false,
      },
    });

    const { fetchAuthProviders } = await import("../api");
    const providers = await fetchAuthProviders();

    expect(providers).toEqual({
      providers: [],
      forceSso: true,
      passwordResetEnabled: false,
    });
  });

  it("falls back to reset enabled when force_sso is false and flag is missing", async () => {
    mockClient.GET.mockResolvedValueOnce({
      data: {
        providers: [],
        force_sso: false,
      },
    });

    const { fetchAuthProviders } = await import("../api");
    const providers = await fetchAuthProviders();

    expect(providers.passwordResetEnabled).toBe(true);
  });
  it("starts MFA enrollment and returns setup details", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          otpauthUri: "otpauth://totp/ADE:user@example.com?secret=ABC123&issuer=ADE",
          issuer: "ADE",
          accountName: "user@example.com",
        }),
        { status: 200 },
      ),
    );

    const { startMfaEnrollment } = await import("../api");
    const payload = await startMfaEnrollment();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/mfa/totp/enroll/start",
      expect.objectContaining({ method: "POST", signal: undefined }),
    );
    expect(payload).toEqual({
      otpauthUri: "otpauth://totp/ADE:user@example.com?secret=ABC123&issuer=ADE",
      issuer: "ADE",
      accountName: "user@example.com",
    });
  });

  it("confirms MFA enrollment and returns recovery codes", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          recoveryCodes: ["ABCD-EFGH", "IJKL-MNOP"],
        }),
        { status: 200 },
      ),
    );

    const { confirmMfaEnrollment } = await import("../api");
    const payload = await confirmMfaEnrollment({ code: "123456" });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/mfa/totp/enroll/confirm",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ code: "123456" }),
      }),
    );
    expect(payload).toEqual({ recoveryCodes: ["ABCD-EFGH", "IJKL-MNOP"] });
  });

  it("disables MFA with the expected endpoint", async () => {
    mockApiFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    const { disableMfa } = await import("../api");
    await disableMfa();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/mfa/totp",
      expect.objectContaining({ method: "DELETE", signal: undefined }),
    );
  });

  it("reads MFA status from the status endpoint", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          enabled: true,
          enrolledAt: "2026-02-01T09:00:00Z",
          recoveryCodesRemaining: 5,
        }),
        { status: 200 },
      ),
    );

    const { fetchMfaStatus } = await import("../api");
    const payload = await fetchMfaStatus();

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/mfa/totp",
      expect.objectContaining({ method: "GET", signal: undefined }),
    );
    expect(payload).toEqual({
      enabled: true,
      enrolledAt: "2026-02-01T09:00:00Z",
      recoveryCodesRemaining: 5,
      onboardingRecommended: false,
      onboardingRequired: false,
      skipAllowed: false,
    });
  });

  it("regenerates MFA recovery codes", async () => {
    mockApiFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          recoveryCodes: ["QWER-TYUI", "ASDF-GHJK"],
        }),
        { status: 200 },
      ),
    );

    const { regenerateMfaRecoveryCodes } = await import("../api");
    const payload = await regenerateMfaRecoveryCodes({ code: "654321" });

    expect(mockApiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/mfa/totp/recovery/regenerate",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ code: "654321" }),
      }),
    );
    expect(payload).toEqual({
      recoveryCodes: ["QWER-TYUI", "ASDF-GHJK"],
    });
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";

import { patchAdminSettings, readAdminSettings } from "../settings";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    PATCH: vi.fn(),
  },
}));

describe("admin settings api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads settings", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        schemaVersion: 2,
        revision: 1,
        values: {
          safeMode: { enabled: false, detail: "Maint" },
          auth: {
            mode: "password_only",
            password: {
              resetEnabled: true,
              mfaRequired: false,
              complexity: {
                minLength: 12,
                requireUppercase: false,
                requireLowercase: false,
                requireNumber: false,
                requireSymbol: false,
              },
              lockout: {
                maxAttempts: 5,
                durationSeconds: 300,
              },
            },
            identityProvider: {
              provisioningMode: "jit",
            },
          },
        },
        meta: {
          safeMode: {
            enabled: { source: "default", lockedByEnv: false, envVar: "ADE_SAFE_MODE", restartRequired: false },
            detail: { source: "default", lockedByEnv: false, envVar: "ADE_SAFE_MODE_DETAIL", restartRequired: false },
          },
          auth: {
            mode: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_MODE", restartRequired: false },
            password: {
              resetEnabled: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_RESET_ENABLED", restartRequired: false },
              mfaRequired: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_MFA_REQUIRED", restartRequired: false },
              complexity: {
                minLength: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_MIN_LENGTH", restartRequired: false },
                requireUppercase: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE", restartRequired: false },
                requireLowercase: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE", restartRequired: false },
                requireNumber: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_NUMBER", restartRequired: false },
                requireSymbol: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL", restartRequired: false },
              },
              lockout: {
                maxAttempts: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS", restartRequired: false },
                durationSeconds: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS", restartRequired: false },
              },
            },
            identityProvider: {
              provisioningMode: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_IDP_PROVISIONING_MODE", restartRequired: false },
            },
          },
        },
        updatedAt: "2026-01-01T00:00:00Z",
        updatedBy: null,
      },
    });

    await readAdminSettings();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/admin/settings", { signal: undefined });
  });

  it("patches settings", async () => {
    (client.PATCH as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        schemaVersion: 2,
        revision: 2,
        values: {
          safeMode: { enabled: true, detail: "Maint" },
          auth: {
            mode: "password_only",
            password: {
              resetEnabled: true,
              mfaRequired: false,
              complexity: {
                minLength: 12,
                requireUppercase: false,
                requireLowercase: false,
                requireNumber: false,
                requireSymbol: false,
              },
              lockout: {
                maxAttempts: 5,
                durationSeconds: 300,
              },
            },
            identityProvider: {
              provisioningMode: "jit",
            },
          },
        },
        meta: {
          safeMode: {
            enabled: { source: "db", lockedByEnv: false, envVar: "ADE_SAFE_MODE", restartRequired: false },
            detail: { source: "db", lockedByEnv: false, envVar: "ADE_SAFE_MODE_DETAIL", restartRequired: false },
          },
          auth: {
            mode: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_MODE", restartRequired: false },
            password: {
              resetEnabled: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_RESET_ENABLED", restartRequired: false },
              mfaRequired: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_MFA_REQUIRED", restartRequired: false },
              complexity: {
                minLength: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_MIN_LENGTH", restartRequired: false },
                requireUppercase: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE", restartRequired: false },
                requireLowercase: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE", restartRequired: false },
                requireNumber: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_NUMBER", restartRequired: false },
                requireSymbol: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL", restartRequired: false },
              },
              lockout: {
                maxAttempts: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS", restartRequired: false },
                durationSeconds: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS", restartRequired: false },
              },
            },
            identityProvider: {
              provisioningMode: { source: "default", lockedByEnv: false, envVar: "ADE_AUTH_IDP_PROVISIONING_MODE", restartRequired: false },
            },
          },
        },
        updatedAt: "2026-01-01T00:00:00Z",
        updatedBy: null,
      },
    });

    await patchAdminSettings({ revision: 1, changes: { safeMode: { enabled: true } } });
    expect(client.PATCH).toHaveBeenCalledWith("/api/v1/admin/settings", {
      body: {
        revision: 1,
        changes: { safeMode: { enabled: true } },
      },
    });
  });
});

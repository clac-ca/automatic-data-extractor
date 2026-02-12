import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SystemSsoSettingsPage } from "../pages/SystemSsoSettingsPage";

const mockUseGlobalPermissions = vi.fn();
const mockUseSsoProvidersQuery = vi.fn();
const mockUseAdminSettingsQuery = vi.fn();
const mockUseCreateSsoProviderMutation = vi.fn();
const mockUseUpdateSsoProviderMutation = vi.fn();
const mockUseValidateSsoProviderMutation = vi.fn();
const mockUsePatchAdminSettingsMutation = vi.fn();
const mockUseScimTokensQuery = vi.fn();
const mockUseCreateScimTokenMutation = vi.fn();
const mockUseRevokeScimTokenMutation = vi.fn();
const mockUseUnsavedChangesGuard = vi.fn();

vi.mock("@/hooks/auth/useGlobalPermissions", () => ({
  useGlobalPermissions: () => mockUseGlobalPermissions(),
}));

vi.mock("@/hooks/admin", () => ({
  useSsoProvidersQuery: () => mockUseSsoProvidersQuery(),
  useAdminSettingsQuery: () => mockUseAdminSettingsQuery(),
  useCreateSsoProviderMutation: () => mockUseCreateSsoProviderMutation(),
  useUpdateSsoProviderMutation: () => mockUseUpdateSsoProviderMutation(),
  useValidateSsoProviderMutation: () => mockUseValidateSsoProviderMutation(),
  usePatchAdminSettingsMutation: () => mockUsePatchAdminSettingsMutation(),
  useScimTokensQuery: () => mockUseScimTokensQuery(),
  useCreateScimTokenMutation: () => mockUseCreateScimTokenMutation(),
  useRevokeScimTokenMutation: () => mockUseRevokeScimTokenMutation(),
}));

vi.mock("@/features/sso-setup", () => ({
  SsoSetupFlow: () => null,
}));

vi.mock(
  "@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard",
  () => ({
    useUnsavedChangesGuard: (...args: unknown[]) => mockUseUnsavedChangesGuard(...args),
  }),
);

function buildSettings(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    schemaVersion: 2,
    revision: 7,
    values: {
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
      safeMode: {
        enabled: false,
        detail: "Safe mode",
      },
    },
    meta: {
      auth: {
        mode: {
          source: "db",
          lockedByEnv: false,
          envVar: "ADE_AUTH_MODE",
          restartRequired: false,
        },
        password: {
          resetEnabled: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_RESET_ENABLED",
            restartRequired: false,
          },
          mfaRequired: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_MFA_REQUIRED",
            restartRequired: false,
          },
          complexity: {
            minLength: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_MIN_LENGTH",
              restartRequired: false,
            },
            requireUppercase: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE",
              restartRequired: false,
            },
            requireLowercase: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE",
              restartRequired: false,
            },
            requireNumber: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_REQUIRE_NUMBER",
              restartRequired: false,
            },
            requireSymbol: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL",
              restartRequired: false,
            },
          },
          lockout: {
            maxAttempts: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS",
              restartRequired: false,
            },
            durationSeconds: {
              source: "db",
              lockedByEnv: false,
              envVar: "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS",
              restartRequired: false,
            },
          },
        },
        identityProvider: {
          provisioningMode: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_IDP_PROVISIONING_MODE",
            restartRequired: false,
          },
        },
      },
      safeMode: {
        enabled: {
          source: "db",
          lockedByEnv: false,
          envVar: "ADE_SAFE_MODE",
          restartRequired: false,
        },
        detail: {
          source: "db",
          lockedByEnv: false,
          envVar: "ADE_SAFE_MODE_DETAIL",
          restartRequired: false,
        },
      },
    },
    updatedAt: "2026-02-01T10:00:00Z",
    updatedBy: null,
    ...overrides,
  } as const;
}

function buildProvider(id: string, status: "active" | "disabled") {
  return {
    id,
    type: "oidc",
    label: id,
    issuer: "https://issuer.example.com",
    clientId: "demo-client",
    status,
    domains: [],
    managedBy: "db",
    locked: false,
    createdAt: "2026-02-01T10:00:00Z",
    updatedAt: "2026-02-01T10:00:00Z",
  } as const;
}

function getMutationStub() {
  return {
    isPending: false,
    mutateAsync: vi.fn(),
  };
}

describe("SystemSsoSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseGlobalPermissions.mockReturnValue({
      hasPermission: () => true,
    });
    mockUseSsoProvidersQuery.mockReturnValue({
      data: { items: [buildProvider("okta-active", "active"), buildProvider("okta-disabled", "disabled")] },
      isLoading: false,
      isError: false,
      error: null,
    });
    mockUseAdminSettingsQuery.mockReturnValue({
      data: buildSettings(),
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    mockUseCreateSsoProviderMutation.mockReturnValue(getMutationStub());
    mockUseUpdateSsoProviderMutation.mockReturnValue(getMutationStub());
    mockUseValidateSsoProviderMutation.mockReturnValue(getMutationStub());
    mockUsePatchAdminSettingsMutation.mockReturnValue(getMutationStub());
    mockUseScimTokensQuery.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      isError: false,
      error: null,
    });
    mockUseCreateScimTokenMutation.mockReturnValue(getMutationStub());
    mockUseRevokeScimTokenMutation.mockReturnValue(getMutationStub());
  });

  it("shows provider lifecycle actions as disable/enable without deleted UI state", () => {
    render(<SystemSsoSettingsPage />);

    expect(screen.getAllByRole("button", { name: "Disable" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole("button", { name: "Enable" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("deleted")).not.toBeInTheDocument();
  });

  it("disables idp-only mode option when no active provider exists", () => {
    mockUseSsoProvidersQuery.mockReturnValue({
      data: { items: [buildProvider("okta-disabled", "disabled")] },
      isLoading: false,
      isError: false,
      error: null,
    });

    render(<SystemSsoSettingsPage />);

    expect(
      screen.getByRole("radio", { name: /Identity provider sign-in only/i }),
    ).toBeDisabled();
  });

  it("shows generic environment lock copy", () => {
    mockUseAdminSettingsQuery.mockReturnValue({
      data: buildSettings({
        meta: {
          ...buildSettings().meta,
          auth: {
            ...buildSettings().meta.auth,
            mode: {
              source: "env",
              lockedByEnv: true,
              envVar: "ADE_AUTH_MODE",
              restartRequired: true,
            },
          },
        },
      }),
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<SystemSsoSettingsPage />);

    expect(
      screen.getByText("Some settings are managed by environment variables and are read-only here."),
    ).toBeInTheDocument();
  });

  it("shows the updated save bar copy when auth policy becomes dirty", async () => {
    const user = userEvent.setup();
    render(<SystemSsoSettingsPage />);

    await user.click(screen.getByRole("radio", { name: /Password \+ identity provider sign-in/i }));
    expect(screen.getByText("Unsaved authentication policy changes.")).toBeInTheDocument();
  });
});

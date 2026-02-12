import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";
import { OrganizationAuthenticationPage } from "../OrganizationAuthenticationPage";

const mockRuntimeQuery = vi.fn();

function buildRuntimeSettings(provisioningMode: "disabled" | "jit" | "scim") {
  return {
    revision: 1,
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
          provisioningMode,
        },
      },
    },
  };
}

function buildMutationStub() {
  return {
    mutateAsync: vi.fn(),
    isPending: false,
  };
}

vi.mock("@/hooks/auth/useGlobalPermissions", () => ({
  useGlobalPermissions: () => ({
    permissions: new Set(["system.settings.manage"]),
  }),
}));

vi.mock("@/pages/Workspace/sections/ConfigurationEditor/workbench/state/useUnsavedChangesGuard", () => ({
  useUnsavedChangesGuard: vi.fn(),
}));

vi.mock("@/features/sso-setup", () => ({
  SsoSetupFlow: () => null,
}));

vi.mock("../../../data", () => ({
  normalizeSettingsError: (_error: unknown, fallback: string) => ({ message: fallback }),
  useOrganizationRuntimeSettingsQuery: (...args: unknown[]) => mockRuntimeQuery(...args),
  useOrganizationSsoProvidersQuery: () => ({
    data: { items: [] },
    isLoading: false,
  }),
  useOrganizationScimTokensQuery: () => ({
    data: { items: [] },
    isLoading: false,
  }),
  usePatchOrganizationRuntimeSettingsMutation: () => buildMutationStub(),
  useCreateOrganizationSsoProviderMutation: () => buildMutationStub(),
  useUpdateOrganizationSsoProviderMutation: () => buildMutationStub(),
  useDeleteOrganizationSsoProviderMutation: () => buildMutationStub(),
  useValidateOrganizationSsoProviderMutation: () => buildMutationStub(),
  useCreateOrganizationScimTokenMutation: () => buildMutationStub(),
  useRevokeOrganizationScimTokenMutation: () => buildMutationStub(),
}));

describe("OrganizationAuthenticationPage", () => {
  beforeEach(() => {
    mockRuntimeQuery.mockReset();
    mockRuntimeQuery.mockReturnValue({
      data: buildRuntimeSettings("jit"),
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  it("shows SCIM recommendation and clarifies JIT behavior", () => {
    render(<OrganizationAuthenticationPage />);

    expect(
      screen.getByText(
        "Use SCIM for enterprise provisioning and group synchronization. JIT auto-provisions users on sign-in only and does not sync groups.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "JIT: auto-provision user identity on successful sign-in only. SCIM (recommended): automatic user provisioning plus group sync.",
      ),
    ).toBeInTheDocument();
  });

  it("hides SCIM token management when provisioning mode is JIT", () => {
    render(<OrganizationAuthenticationPage />);
    expect(screen.queryByRole("button", { name: "Create token" })).not.toBeInTheDocument();
  });

  it("shows SCIM token management when provisioning mode is SCIM", () => {
    mockRuntimeQuery.mockReturnValue({
      data: buildRuntimeSettings("scim"),
      isLoading: false,
      isError: false,
      error: null,
    });
    render(<OrganizationAuthenticationPage />);
    expect(screen.getByRole("button", { name: "Create token" })).toBeInTheDocument();
  });
});

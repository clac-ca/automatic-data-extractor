import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@test/test-utils";
import LoginScreen from "@pages/Login";

const mockUseSessionQuery = vi.fn();
const mockUseSetupStatusQuery = vi.fn();
const mockUseAuthProvidersQuery = vi.fn();

vi.mock("@hooks/auth/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

vi.mock("@hooks/auth/useSetupStatusQuery", () => ({
  useSetupStatusQuery: (enabled?: boolean) => mockUseSetupStatusQuery(enabled),
}));

vi.mock("@hooks/auth/useAuthProvidersQuery", () => ({
  useAuthProvidersQuery: () => mockUseAuthProvidersQuery(),
}));

function renderWithPath(path: string) {
  window.history.replaceState(null, "", path);
  return render(<LoginScreen />);
}

describe("LoginScreen SSO UX", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
    mockUseSetupStatusQuery.mockReset();
    mockUseAuthProvidersQuery.mockReset();

    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    mockUseSetupStatusQuery.mockReturnValue({
      data: {
        setup_required: false,
        registration_mode: "closed",
        oidc_configured: false,
        providers: [],
      },
      isPending: false,
      isError: false,
      isSuccess: true,
      refetch: vi.fn(),
    });

    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], forceSso: false },
      isError: false,
      isFetching: false,
      isLoading: false,
    });
  });

  it("renders provider buttons with the sanitized returnTo", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        forceSso: false,
        providers: [
          {
            id: "okta",
            label: "Okta",
            type: "oidc",
            startUrl: "/api/v1/auth/sso/okta/authorize",
          },
        ],
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login?returnTo=/workspaces/alpha");

    const link = screen.getByRole("link", { name: "Continue with Okta" });
    expect(link).toHaveAttribute(
      "href",
      "/api/v1/auth/sso/okta/authorize?returnTo=%2Fworkspaces%2Falpha",
    );
  });

  it("sanitizes unsafe returnTo values before building SSO URLs", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        forceSso: false,
        providers: [
          {
            id: "okta",
            label: "Okta",
            type: "oidc",
            startUrl: "/api/v1/auth/sso/okta/authorize",
          },
        ],
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login?returnTo=//evil.example.com");

    const link = screen.getByRole("link", { name: "Continue with Okta" });
    expect(link).toHaveAttribute("href", "/api/v1/auth/sso/okta/authorize?returnTo=%2F");
  });

  it("shows a blocking error when forceSso is enabled without providers", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], forceSso: true },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login");

    expect(
      screen.getByText(
        "Single sign-on is required, but no providers are available. Contact your administrator.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText(/email address/i)).not.toBeInTheDocument();
  });

  it("keeps password login available when providers fail to load and forceSso is false", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], forceSso: false },
      isError: true,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login");

    expect(
      screen.getByText(
        "We couldn't load the list of providers. Refresh the page or continue with email.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
  });

  it("maps backend ssoError codes to deterministic messages", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        forceSso: false,
        providers: [
          {
            id: "okta",
            label: "Okta",
            type: "oidc",
            startUrl: "/api/v1/auth/sso/okta/authorize",
          },
        ],
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login?ssoError=PROVIDER_MISCONFIGURED&providerId=okta");

    expect(
      screen.getByText(
        "Okta sign-in failed. The provider is misconfigured. Contact your administrator.",
      ),
    ).toBeInTheDocument();
  });

  it("surfaces missing email errors from the IdP", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        forceSso: false,
        providers: [
          {
            id: "okta",
            label: "Okta",
            type: "oidc",
            startUrl: "/api/v1/auth/sso/okta/authorize",
          },
        ],
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login?ssoError=EMAIL_MISSING&providerId=okta");

    expect(
      screen.getByText(
        "Okta sign-in failed. Your identity provider did not return an email address.",
      ),
    ).toBeInTheDocument();
  });

  it("surfaces auto-provisioning disabled errors", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        forceSso: false,
        providers: [
          {
            id: "okta",
            label: "Okta",
            type: "oidc",
            startUrl: "/api/v1/auth/sso/okta/authorize",
          },
        ],
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login?ssoError=AUTO_PROVISION_DISABLED&providerId=okta");

    expect(
      screen.getByText(
        "Okta sign-in failed. Your account must be provisioned before signing in.",
      ),
    ).toBeInTheDocument();
  });
});

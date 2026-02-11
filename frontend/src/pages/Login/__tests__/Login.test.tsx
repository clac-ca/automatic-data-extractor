import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import { render, screen } from "@/test/test-utils";
import LoginScreen from "@/pages/Login";

const mockUseSessionQuery = vi.fn();
const mockUseSetupStatusQuery = vi.fn();
const mockUseAuthProvidersQuery = vi.fn();
const mockCreateSession = vi.fn();
const mockVerifyMfaChallenge = vi.fn();

vi.mock("@/api/auth/api", async () => {
  const actual = await vi.importActual<typeof import("@/api/auth/api")>("@/api/auth/api");
  return {
    ...actual,
    createSession: (...args: unknown[]) => mockCreateSession(...args),
    verifyMfaChallenge: (...args: unknown[]) => mockVerifyMfaChallenge(...args),
  };
});

vi.mock("@/hooks/auth/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

vi.mock("@/hooks/auth/useSetupStatusQuery", () => ({
  useSetupStatusQuery: (enabled?: boolean) => mockUseSetupStatusQuery(enabled),
}));

vi.mock("@/hooks/auth/useAuthProvidersQuery", () => ({
  useAuthProvidersQuery: () => mockUseAuthProvidersQuery(),
}));

function renderWithPath(path: string) {
  window.history.replaceState(null, "", path);
  return render(<LoginScreen />);
}

describe("LoginScreen", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
    mockUseSetupStatusQuery.mockReset();
    mockUseAuthProvidersQuery.mockReset();
    mockCreateSession.mockReset();
    mockVerifyMfaChallenge.mockReset();

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
      data: { providers: [], mode: "password_only", passwordResetEnabled: true },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    mockCreateSession.mockResolvedValue({
      kind: "session",
      session: {
        user: {
          id: "user-1",
          email: "user@example.com",
          display_name: "User",
          global_roles: [],
          workspace_roles: {},
          is_active: true,
          preferred_workspace_id: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          roles: [],
          permissions: [],
        },
        workspaces: [],
        roles: [],
        permissions: [],
        return_to: "/",
      },
      mfaSetupRecommended: false,
      mfaSetupRequired: false,
    });
    mockVerifyMfaChallenge.mockResolvedValue({
      user: {
        id: "user-1",
        email: "user@example.com",
        display_name: "User",
        global_roles: [],
        workspace_roles: {},
        is_active: true,
        preferred_workspace_id: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        roles: [],
        permissions: [],
      },
      workspaces: [],
      roles: [],
      permissions: [],
      return_to: "/",
    });
  });

  it("renders provider buttons with the sanitized returnTo", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        mode: "password_and_idp",
        passwordResetEnabled: true,
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
        mode: "password_and_idp",
        passwordResetEnabled: true,
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

  it("shows global-admin break-glass path in idp-only mode", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], mode: "idp_only", passwordResetEnabled: false },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login");

    expect(screen.getByText("Identity provider sign-in is required for organization members.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/email address/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Global admin password sign-in" })).toBeInTheDocument();
  });

  it("keeps password login available when provider load fails in password mode", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], mode: "password_only", passwordResetEnabled: true },
      isError: true,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login");

    expect(
      screen.getByText(
        "We couldn't load identity provider options. Refresh the page or continue with password sign-in.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
  });

  it("maps backend ssoError codes to deterministic messages", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        mode: "password_and_idp",
        passwordResetEnabled: true,
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

  it("maps EMAIL_LINK_UNVERIFIED to an actionable SSO message", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        mode: "password_and_idp",
        passwordResetEnabled: true,
        providers: [
          {
            id: "entra",
            label: "Microsoft Entra ID",
            type: "oidc",
            startUrl: "/api/v1/auth/sso/authorize",
          },
        ],
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login?ssoError=EMAIL_LINK_UNVERIFIED&providerId=entra");

    expect(
      screen.getByText(
        "Microsoft Entra ID sign-in failed. We couldn't safely link this sign-in to an existing account. Contact your administrator.",
      ),
    ).toBeInTheDocument();
  });

  it("hides forgot-password entry when password reset is disabled", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], mode: "password_only", passwordResetEnabled: false },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    renderWithPath("/login");

    expect(screen.queryByRole("link", { name: "Forgot your password?" })).not.toBeInTheDocument();
    expect(
      screen.getByText("Password reset is unavailable. Contact your administrator."),
    ).toBeInTheDocument();
  });

  it("uses password-manager friendly metadata on password login fields", () => {
    renderWithPath("/login");

    const emailInput = screen.getByLabelText(/email address/i);
    expect(emailInput).toHaveAttribute("autocomplete", "username");
    expect(emailInput).toHaveAttribute("autocapitalize", "none");
    expect(emailInput).toHaveAttribute("autocorrect", "off");
    expect(emailInput).toHaveAttribute("spellcheck", "false");

    const passwordInput = screen.getByLabelText(/password/i);
    expect(passwordInput).toHaveAttribute("autocomplete", "current-password");
    expect(passwordInput).toHaveAttribute("autocapitalize", "none");
    expect(passwordInput).toHaveAttribute("autocorrect", "off");
    expect(passwordInput).toHaveAttribute("spellcheck", "false");
  });

  it("shows an email-login separator when both SSO and password login are available", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        forceSso: false,
        passwordResetEnabled: true,
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

    renderWithPath("/login");

    expect(screen.getByText("or continue with email")).toBeInTheDocument();
  });

  it("switches to the MFA challenge step with one smart input", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });

    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByText("Step 2 of 2")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Verify your identity" })).toBeInTheDocument();
    expect(screen.queryByText("Verification method")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Authenticator app" })).not.toBeInTheDocument();
    expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument();
  });

  it("keeps one-time-code autocomplete on MFA input", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    const codeInput = await screen.findByLabelText(/verification code/i);
    expect(codeInput).toHaveAttribute("autocomplete", "one-time-code");
  });

  it("detects OTP-style input and submits a 6-digit code", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    mockVerifyMfaChallenge.mockRejectedValueOnce(new Error("keep-on-mfa"));
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    const codeInput = await screen.findByLabelText(/verification code/i);
    expect(codeInput).toHaveAttribute("inputmode", "numeric");

    await user.type(codeInput, "12 34 56");
    expect(codeInput).toHaveValue("123456");
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));

    expect(mockVerifyMfaChallenge).toHaveBeenLastCalledWith({
      challengeToken: "challenge-1",
      code: "123456",
    });
  });

  it("auto-detects recovery codes and submits normalized recovery format", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    mockVerifyMfaChallenge.mockRejectedValueOnce(new Error("keep-on-mfa"));
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    const codeInput = await screen.findByLabelText(/verification code/i);
    await user.type(codeInput, "ab12-3cd4xx");

    expect(codeInput).toHaveValue("AB12-3CD4");
    expect(codeInput).toHaveAttribute("inputmode", "text");
    expect(screen.getByText("Recovery code detected.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Verify and continue" }));
    expect(mockVerifyMfaChallenge).toHaveBeenLastCalledWith({
      challengeToken: "challenge-1",
      code: "AB12-3CD4",
    });
  });

  it("shows strict field-level validation for ambiguous 7-digit input", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByLabelText(/verification code/i), "1234567");
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));

    expect(
      await screen.findByText("Enter a 6-digit authenticator code or an 8-character recovery code."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("reveals subtle fallback guidance after two invalid submissions", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    mockVerifyMfaChallenge
      .mockRejectedValueOnce(
        new ApiError(
          "Invalid one-time password.",
          400,
          { detail: "Invalid one-time password." } as unknown as ApiError["problem"],
        ),
      )
      .mockRejectedValueOnce(
        new ApiError(
          "Invalid one-time password.",
          400,
          { detail: "Invalid one-time password." } as unknown as ApiError["problem"],
        ),
      );
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));

    const codeInput = await screen.findByLabelText(/verification code/i);
    await user.type(codeInput, "123456");
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));

    expect(await screen.findByText("Having trouble with your code?")).toBeInTheDocument();
    expect(
      screen.getByText("This field also accepts recovery codes (example: AB12-3CD4)."),
    ).toBeInTheDocument();
  });

  it("maps MFA API errors with assertive alerts", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    mockVerifyMfaChallenge.mockRejectedValueOnce(
      new ApiError(
        "Invalid one-time password.",
        400,
        { detail: "Invalid one-time password." } as unknown as ApiError["problem"],
      ),
    );
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByLabelText(/verification code/i), "123456");
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));

    const errorAlert = await screen.findByRole("alert");
    expect(errorAlert).toHaveAttribute("aria-live", "assertive");
    expect(errorAlert).toHaveTextContent("That code wasn't accepted. Check the code and try again.");
  });

  it("maps expired MFA challenge errors to a restart message", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    mockVerifyMfaChallenge.mockRejectedValueOnce(
      new ApiError(
        "MFA challenge is invalid or expired.",
        400,
        { detail: "MFA challenge is invalid or expired." } as unknown as ApiError["problem"],
      ),
    );
    renderWithPath("/login");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(await screen.findByLabelText(/verification code/i), "123456");
    await user.click(screen.getByRole("button", { name: "Verify and continue" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Your verification session expired. Sign in again.",
    );
  });

  it("keeps the email value when returning from MFA to password login", async () => {
    const user = userEvent.setup();
    mockCreateSession.mockResolvedValueOnce({
      kind: "mfa_required",
      challengeToken: "challenge-1",
    });
    renderWithPath("/login");

    const emailInput = screen.getByLabelText(/email address/i);
    await user.type(emailInput, "remember.me@example.com");
    await user.type(screen.getByLabelText(/password/i), "notsecret1!Ab");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(await screen.findByRole("button", { name: "Back to password login" }));

    expect(await screen.findByLabelText(/email address/i)).toHaveValue("remember.me@example.com");
  });
});

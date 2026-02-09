import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import { render, screen } from "@/test/test-utils";
import ForgotPasswordScreen from "@/pages/ForgotPassword";

const mockUseSessionQuery = vi.fn();
const mockUseSetupStatusQuery = vi.fn();
const mockUseAuthProvidersQuery = vi.fn();
const mockRequestPasswordReset = vi.fn();

vi.mock("@/hooks/auth/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

vi.mock("@/hooks/auth/useSetupStatusQuery", () => ({
  useSetupStatusQuery: (enabled?: boolean) => mockUseSetupStatusQuery(enabled),
}));

vi.mock("@/hooks/auth/useAuthProvidersQuery", () => ({
  useAuthProvidersQuery: () => mockUseAuthProvidersQuery(),
}));

vi.mock("@/api/auth/api", () => ({
  requestPasswordReset: (...args: unknown[]) => mockRequestPasswordReset(...args),
}));

function renderWithPath(path: string) {
  window.history.replaceState(null, "", path);
  return render(<ForgotPasswordScreen />);
}

describe("ForgotPasswordScreen", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
    mockUseSetupStatusQuery.mockReset();
    mockUseAuthProvidersQuery.mockReset();
    mockRequestPasswordReset.mockReset();

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
      data: {
        providers: [],
        mode: "password_only",
        passwordResetEnabled: true,
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });

    mockRequestPasswordReset.mockResolvedValue(undefined);
  });

  it("links back to login while preserving safe returnTo", () => {
    renderWithPath("/forgot-password?returnTo=/workspaces/alpha");

    const link = screen.getByRole("link", { name: "Back to sign in" });
    expect(link).toHaveAttribute("href", "/login?returnTo=%2Fworkspaces%2Falpha");
  });

  it("shows a uniform confirmation message after successful submit", async () => {
    const user = userEvent.setup();
    renderWithPath("/forgot-password");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset instructions" }));

    expect(mockRequestPasswordReset).toHaveBeenCalledWith({ email: "user@example.com" });
    expect(
      await screen.findByText(
        "If an account exists for that email, password reset instructions will be sent shortly.",
      ),
    ).toBeInTheDocument();
  });

  it("surfaces network/api failures", async () => {
    const user = userEvent.setup();
    mockRequestPasswordReset.mockRejectedValueOnce(new Error("network unavailable"));
    renderWithPath("/forgot-password");

    await user.type(screen.getByLabelText(/email address/i), "user@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset instructions" }));

    expect(await screen.findByText("network unavailable")).toBeInTheDocument();
  });

  it("shows unavailable messaging when password reset is turned off", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        providers: [],
        mode: "password_only",
        passwordResetEnabled: false,
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });
    renderWithPath("/forgot-password");

    expect(screen.queryByLabelText(/email address/i)).not.toBeInTheDocument();
    expect(
      screen.getByText("Password reset is unavailable. Contact your administrator."),
    ).toBeInTheDocument();
  });

  it("shows SSO-unavailable messaging when idp-only mode disables reset", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: {
        providers: [],
        mode: "idp_only",
        passwordResetEnabled: false,
      },
      isError: false,
      isFetching: false,
      isLoading: false,
    });
    mockRequestPasswordReset.mockRejectedValueOnce(
      new ApiError(
        "forbidden",
        403,
        { detail: "Password reset is unavailable." } as unknown as ApiError["problem"],
      ),
    );
    renderWithPath("/forgot-password");

    expect(
      screen.getByText(
        "Password reset is managed by your organization's identity provider. Use SSO sign-in or contact your administrator.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send reset instructions" })).not.toBeInTheDocument();
  });
});

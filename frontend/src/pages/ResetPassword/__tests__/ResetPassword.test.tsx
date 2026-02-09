import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api";
import { render, screen } from "@/test/test-utils";
import ResetPasswordScreen from "@/pages/ResetPassword";

const navigateMock = vi.fn();
const mockUseAuthProvidersQuery = vi.fn();
const mockCompletePasswordReset = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("@/api/auth/api", () => ({
  completePasswordReset: (...args: unknown[]) => mockCompletePasswordReset(...args),
}));

vi.mock("@/hooks/auth/useAuthProvidersQuery", () => ({
  useAuthProvidersQuery: () => mockUseAuthProvidersQuery(),
}));

function renderWithPath(path: string) {
  window.history.replaceState(null, "", path);
  return render(<ResetPasswordScreen />);
}

describe("ResetPasswordScreen", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    mockUseAuthProvidersQuery.mockReset();
    mockCompletePasswordReset.mockReset();
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], mode: "password_only", passwordResetEnabled: true },
      isError: false,
      isFetching: false,
      isLoading: false,
    });
    mockCompletePasswordReset.mockResolvedValue(undefined);
  });

  it("validates password length before submitting", async () => {
    const user = userEvent.setup();
    renderWithPath("/reset-password?token=token-123");

    await user.type(screen.getByPlaceholderText("••••••••••••"), "short");
    await user.type(screen.getByPlaceholderText("Re-enter your new password"), "short");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(screen.getAllByText("Use at least 12 characters.")).toHaveLength(2);
    expect(mockCompletePasswordReset).not.toHaveBeenCalled();
  });

  it("validates matching confirmation password", async () => {
    const user = userEvent.setup();
    renderWithPath("/reset-password?token=token-123");

    await user.type(screen.getByPlaceholderText("••••••••••••"), "notsecret3!Ab");
    await user.type(screen.getByPlaceholderText("Re-enter your new password"), "differentpassword");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(mockCompletePasswordReset).not.toHaveBeenCalled();
  });

  it("submits and redirects to login success banner", async () => {
    const user = userEvent.setup();
    renderWithPath("/reset-password?token=token-abc&returnTo=/workspaces/alpha");

    await user.type(screen.getByPlaceholderText("••••••••••••"), "notsecret3!Ab");
    await user.type(screen.getByPlaceholderText("Re-enter your new password"), "notsecret3!Ab");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(mockCompletePasswordReset).toHaveBeenCalledWith({
      token: "token-abc",
      newPassword: "notsecret3!Ab",
    });
    expect(navigateMock).toHaveBeenCalledWith(
      "/login?passwordReset=success&returnTo=%2Fworkspaces%2Falpha",
      { replace: true },
    );
  });

  it("surfaces backend invalid-token errors", async () => {
    const user = userEvent.setup();
    mockCompletePasswordReset.mockRejectedValueOnce(
      new ApiError(
        "Request failed",
        400,
        { detail: "Reset token is invalid or expired." } as unknown as ApiError["problem"],
      ),
    );
    renderWithPath("/reset-password?token=expired-token");

    await user.type(screen.getByPlaceholderText("••••••••••••"), "notsecret3!Ab");
    await user.type(screen.getByPlaceholderText("Re-enter your new password"), "notsecret3!Ab");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    expect(await screen.findByText("Reset token is invalid or expired.")).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("shows a clear warning when the token is missing from the URL", () => {
    renderWithPath("/reset-password");

    expect(
      screen.getByText(
        "This reset link is missing its token. Request a new password reset email and use the full link.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset password" })).toBeDisabled();
  });

  it("shows disabled messaging when password reset is turned off", () => {
    mockUseAuthProvidersQuery.mockReturnValue({
      data: { providers: [], mode: "password_only", passwordResetEnabled: false },
      isError: false,
      isFetching: false,
      isLoading: false,
    });
    renderWithPath("/reset-password?token=abc123");

    expect(screen.queryByRole("button", { name: "Reset password" })).not.toBeInTheDocument();
    expect(
      screen.getByText("Password reset is unavailable. Contact your administrator."),
    ).toBeInTheDocument();
  });
});

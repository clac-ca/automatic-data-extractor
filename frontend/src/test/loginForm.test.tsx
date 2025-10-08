import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LoginForm } from "../features/auth/components/LoginForm";
import { ApiError } from "../shared/api/client";

const mutateAsync = vi.fn();

vi.mock("../features/auth/hooks/useLoginMutation", () => ({
  useLoginMutation: () => ({ mutateAsync, isPending: false }),
}));

describe("LoginForm", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
  });

  it("validates required fields", async () => {
    const user = userEvent.setup();
    render(<LoginForm providers={[]} forceSso={false} />);

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/enter your email/i)).toBeInTheDocument();
    expect(await screen.findByText(/enter your password/i)).toBeInTheDocument();
  });

  it("surfaces API errors", async () => {
    const user = userEvent.setup();
    const error = new ApiError("Invalid credentials", 401, {
      title: "Invalid credentials",
      detail: "Email or password is incorrect",
      errors: { email: ["Unknown account"] },
    });

    mutateAsync.mockRejectedValueOnce(error);

    render(<LoginForm providers={[]} forceSso={false} />);

    await user.type(screen.getByLabelText(/email/i), "ada@example.com");
    await user.type(screen.getByLabelText(/password/i), "password123!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/email or password is incorrect/i)).toBeInTheDocument();
    expect(screen.getByText(/unknown account/i)).toBeInTheDocument();
  });

  it("renders provider CTA when SSO is enforced", () => {
    render(
      <LoginForm
        forceSso
        providers={[{ id: "entra", label: "Microsoft Entra", start_url: "https://login" }]}
      />,
    );

    expect(screen.getByText(/single sign-on required/i)).toBeInTheDocument();
    expect(screen.getByText(/continue with microsoft entra/i)).toBeInTheDocument();
  });
});

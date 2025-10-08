import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SetupWizard } from "../features/setup/components/SetupWizard";
import { ApiError } from "../shared/api/client";

const mutateAsync = vi.fn();

vi.mock("../features/setup/hooks/useCompleteSetupMutation", () => ({
  useCompleteSetupMutation: () => ({ mutateAsync, isPending: false }),
}));

describe("SetupWizard", () => {
  beforeEach(() => {
    mutateAsync.mockReset();
  });

  it("validates administrator form", async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);

    await user.click(screen.getByRole("button", { name: /begin setup/i }));
    await user.click(screen.getByRole("button", { name: /create administrator/i }));

    expect(await screen.findByText(/provide a display name/i)).toBeInTheDocument();
    expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/password must be at least 12 characters/i)).toBeInTheDocument();
  });

  it("shows completion state on success", async () => {
    const user = userEvent.setup();
    mutateAsync.mockResolvedValueOnce(undefined);

    render(<SetupWizard />);

    await user.click(screen.getByRole("button", { name: /begin setup/i }));
    await user.type(screen.getByLabelText(/display name/i), "Ada Lovelace");
    await user.type(screen.getByLabelText(/^email/i), "ada@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "Password1234");
    await user.type(screen.getByLabelText(/confirm password/i), "Password1234");
    await user.click(screen.getByRole("button", { name: /create administrator/i }));

    expect(await screen.findByText(/setup complete/i)).toBeInTheDocument();
  });

  it("maps API errors to fields", async () => {
    const user = userEvent.setup();
    mutateAsync.mockRejectedValueOnce(
      new ApiError("Conflict", 409, {
        title: "Conflict",
        detail: "Administrator already exists",
        errors: { email: ["Email already in use"] },
      }),
    );

    render(<SetupWizard />);

    await user.click(screen.getByRole("button", { name: /begin setup/i }));
    await user.type(screen.getByLabelText(/display name/i), "Ada Lovelace");
    await user.type(screen.getByLabelText(/^email/i), "ada@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "Password1234");
    await user.type(screen.getByLabelText(/confirm password/i), "Password1234");
    await user.click(screen.getByRole("button", { name: /create administrator/i }));

    expect(await screen.findByText(/administrator already exists/i)).toBeInTheDocument();
    expect(screen.getByText(/email already in use/i)).toBeInTheDocument();
  });
});

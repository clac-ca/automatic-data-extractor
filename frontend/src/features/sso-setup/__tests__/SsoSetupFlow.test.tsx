import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@testing-library/react";
import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SsoProviderAdmin } from "@/api/admin/sso";
import { ApiError } from "@/api/errors";
import { SsoSetupFlow } from "../SsoSetupFlow";

function buildProvider(overrides: Partial<SsoProviderAdmin> = {}): SsoProviderAdmin {
  return {
    id: "okta-primary",
    type: "oidc",
    label: "Okta",
    issuer: "https://issuer.example.com",
    clientId: "demo-client",
    status: "active",
    domains: ["example.com"],
    managedBy: "db",
    locked: false,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function setup(overrides: Partial<ComponentProps<typeof SsoSetupFlow>> = {}) {
  const onOpenChange = vi.fn();
  const onValidate = vi.fn().mockResolvedValue({
    issuer: "https://issuer.example.com",
    authorizationEndpoint: "https://issuer.example.com/oauth2/v1/authorize",
    tokenEndpoint: "https://issuer.example.com/oauth2/v1/token",
    jwksUri: "https://issuer.example.com/oauth2/v1/keys",
  });
  const onCreate = vi.fn().mockResolvedValue(undefined);
  const onUpdate = vi.fn().mockResolvedValue(undefined);
  const onSuccess = vi.fn();

  render(
    <SsoSetupFlow
      open
      mode="create"
      canManage
      isSubmitting={false}
      isValidating={false}
      onOpenChange={onOpenChange}
      onValidate={onValidate}
      onCreate={onCreate}
      onUpdate={onUpdate}
      onSuccess={onSuccess}
      {...overrides}
    />,
  );

  return {
    onOpenChange,
    onValidate,
    onCreate,
    onUpdate,
    onSuccess,
  };
}

async function fillCreateFormToTestStep(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.type(await screen.findByLabelText(/Provider ID/i), "okta-primary");
  await user.type(screen.getByLabelText(/Label/i), "Okta Workforce");
  await user.type(screen.getByLabelText(/Allowed domains/i), "example.com");
  await user.click(screen.getByRole("button", { name: "Continue" }));

  await user.type(await screen.findByLabelText(/Issuer/i), "https://issuer.example.com");
  await user.type(screen.getByLabelText(/Client ID/i), "demo-client");
  await user.type(screen.getByLabelText(/Client secret/i), "notsecret-client");
  await user.click(screen.getByRole("button", { name: "Continue" }));
}

describe("SsoSetupFlow", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("disables continue on test step until validation passes", async () => {
    const user = userEvent.setup();
    setup();

    await fillCreateFormToTestStep(user);
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("saves provider after successful validation", async () => {
    const user = userEvent.setup();
    const { onValidate, onCreate, onOpenChange, onSuccess } = setup();

    await fillCreateFormToTestStep(user);
    await user.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() =>
      expect(onValidate).toHaveBeenCalledWith({
        issuer: "https://issuer.example.com",
        clientId: "demo-client",
        clientSecret: "notsecret-client",
      }),
    );

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Save provider" }));

    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith({
        id: "okta-primary",
        type: "oidc",
        label: "Okta Workforce",
        issuer: "https://issuer.example.com",
        clientId: "demo-client",
        clientSecret: "notsecret-client",
        status: "active",
        domains: ["example.com"],
      }),
    );
    expect(onSuccess).toHaveBeenCalledWith(
      "Provider saved. Review authentication policy before requiring identity provider sign-in.",
    );
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("shows inline discard confirmation before closing dirty setup state", async () => {
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    const { onOpenChange } = setup();

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.type(screen.getByLabelText(/Provider ID/i), "okta-primary");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByText("Discard setup changes?")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Discard setup changes?" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Discard changes" }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("skips validation for edit-only non-connection changes", async () => {
    const user = userEvent.setup();
    const provider = buildProvider();
    const { onUpdate } = setup({
      mode: "edit",
      provider,
    });

    await user.click(screen.getByRole("button", { name: "Continue" }));
    const labelField = screen.getByLabelText(/Label/i);
    await user.clear(labelField);
    await user.type(labelField, "Okta Renamed");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(
      screen.getByText("No connection test is required for this change. Continue to review and save."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("button", { name: "Save provider" }));

    await waitFor(() =>
      expect(onUpdate).toHaveBeenCalledWith("okta-primary", {
        label: "Okta Renamed",
        issuer: "https://issuer.example.com",
        clientId: "demo-client",
        clientSecret: undefined,
        status: "active",
        domains: ["example.com"],
      }),
    );
  });

  it("shows actionable validation remediation for issuer mismatch", async () => {
    const user = userEvent.setup();
    const { onValidate } = setup();
    onValidate.mockRejectedValueOnce(
      new ApiError("Request failed with status 422", 422, {
        type: "validation_error",
        title: "Validation error",
        status: 422,
        detail: "Issuer validation failed because discovery metadata issuer did not match.",
        errors: [
          {
            path: "issuer",
            code: "sso_issuer_mismatch",
            message: "Issuer mismatch",
          },
        ],
      }),
    );

    await fillCreateFormToTestStep(user);
    await user.click(screen.getByRole("button", { name: "Test connection" }));

    expect(
      screen.getByText("Issuer mismatch. Confirm the issuer URL exactly matches the metadata issuer."),
    ).toBeInTheDocument();
  });
});

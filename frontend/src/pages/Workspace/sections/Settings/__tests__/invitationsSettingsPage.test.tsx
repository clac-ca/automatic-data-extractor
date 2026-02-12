import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InvitationsSettingsPage } from "../pages/InvitationsSettingsPage";

const mockUseWorkspaceContext = vi.fn();
const mockUseWorkspaceInvitationsQuery = vi.fn();
const mockUseResendWorkspaceInvitationMutation = vi.fn();
const mockUseCancelWorkspaceInvitationMutation = vi.fn();
const mockUseWorkspaceRolesQuery = vi.fn();

vi.mock("@/pages/Workspace/context/WorkspaceContext", () => ({
  useWorkspaceContext: () => mockUseWorkspaceContext(),
}));

vi.mock("../hooks/useWorkspaceInvitations", () => ({
  useWorkspaceInvitationsQuery: (...args: unknown[]) => mockUseWorkspaceInvitationsQuery(...args),
  useResendWorkspaceInvitationMutation: (...args: unknown[]) =>
    mockUseResendWorkspaceInvitationMutation(...args),
  useCancelWorkspaceInvitationMutation: (...args: unknown[]) =>
    mockUseCancelWorkspaceInvitationMutation(...args),
}));

vi.mock("../hooks/useWorkspaceRoles", () => ({
  useWorkspaceRolesQuery: (...args: unknown[]) => mockUseWorkspaceRolesQuery(...args),
}));

function buildInvitation(id: string) {
  return {
    id,
    email_normalized: `${id}@example.com`,
    invited_user_id: null,
    invited_by_user_id: "admin",
    status: "pending",
    expires_at: "2030-01-01T00:00:00Z",
    redeemed_at: null,
    metadata: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  } as const;
}

describe("InvitationsSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWorkspaceContext.mockReturnValue({
      workspace: { id: "ws-1" },
      hasPermission: (permission: string) =>
        permission === "workspace.invitations.read" || permission === "workspace.invitations.manage",
    });
    mockUseWorkspaceInvitationsQuery.mockReturnValue({
      data: { items: [buildInvitation("invite-one")] },
      isLoading: false,
      isError: false,
      error: null,
    });
    mockUseResendWorkspaceInvitationMutation.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue(buildInvitation("invite-one")),
    });
    mockUseCancelWorkspaceInvitationMutation.mockReturnValue({
      isPending: false,
      mutateAsync: vi.fn().mockResolvedValue(buildInvitation("invite-one")),
    });
    mockUseWorkspaceRolesQuery.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  it("blocks access without invitation permissions", () => {
    mockUseWorkspaceContext.mockReturnValue({
      workspace: { id: "ws-1" },
      hasPermission: () => false,
    });

    render(<InvitationsSettingsPage />);

    expect(screen.getByText("You do not have permission to access workspace invitations.")).toBeInTheDocument();
  });

  it("renders invitations and allows resend/cancel when management permission is present", async () => {
    const user = userEvent.setup();
    const resend = vi.fn().mockResolvedValue(buildInvitation("invite-one"));
    const cancel = vi.fn().mockResolvedValue(buildInvitation("invite-one"));
    mockUseResendWorkspaceInvitationMutation.mockReturnValue({
      isPending: false,
      mutateAsync: resend,
    });
    mockUseCancelWorkspaceInvitationMutation.mockReturnValue({
      isPending: false,
      mutateAsync: cancel,
    });

    render(<InvitationsSettingsPage />);

    expect(screen.getByText("Workspace invitations")).toBeInTheDocument();
    expect(screen.getByText("invite-one@example.com")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Invitation actions" }));
    await user.click(screen.getByRole("menuitem", { name: "Resend invitation" }));
    expect(resend).toHaveBeenCalledWith("invite-one");
    expect(await screen.findByText("Invitation resent.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Invitation actions" }));
    await user.click(screen.getByRole("menuitem", { name: "Cancel invitation" }));
    await user.click(screen.getByRole("button", { name: "Cancel invitation" }));
    expect(cancel).toHaveBeenCalledWith("invite-one");
    expect(await screen.findByText("Invitation canceled.")).toBeInTheDocument();
  });
});

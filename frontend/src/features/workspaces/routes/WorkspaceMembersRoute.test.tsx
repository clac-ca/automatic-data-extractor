import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";

import type { RoleDefinition, WorkspaceMember, WorkspaceProfile } from "../../../shared/api/types";

const useWorkspaceMembersQueryMock = vi.fn();
const useWorkspaceRolesQueryMock = vi.fn();

vi.mock("../hooks/useWorkspaceMembersQuery", () => ({
  useWorkspaceMembersQuery: (...args: unknown[]) => useWorkspaceMembersQueryMock(...args),
}));

vi.mock("../hooks/useWorkspaceRolesQuery", () => ({
  useWorkspaceRolesQuery: (...args: unknown[]) => useWorkspaceRolesQueryMock(...args),
}));

const mockWorkspace: WorkspaceProfile = {
  id: "workspace-1",
  name: "Finance",
  slug: "finance",
  roles: ["workspace-owner"],
  permissions: ["Workspace.Members.Read", "Workspace.Members.ReadWrite", "Workspace.Roles.Read"],
  is_default: false,
};

const useOutletContextMock = vi.fn(() => ({ workspace: mockWorkspace }));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useOutletContext: () => useOutletContextMock(),
  };
});

import { WorkspaceMembersRoute } from "./WorkspaceMembersRoute";

describe("WorkspaceMembersRoute", () => {
  beforeEach(() => {
    useWorkspaceMembersQueryMock.mockReset();
    useWorkspaceRolesQueryMock.mockReset();
    useOutletContextMock.mockReset();
    useOutletContextMock.mockReturnValue({ workspace: mockWorkspace });
  });

  it("renders member details", () => {
    const member: WorkspaceMember = {
      id: "membership-1",
      workspace_id: "workspace-1",
      roles: ["workspace-owner"],
      permissions: ["Workspace.Settings.ReadWrite"],
      is_default: true,
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "User One",
        roles: ["global-user"],
        permissions: [],
      },
    };
    const roles: RoleDefinition[] = [
      {
        id: "role-1",
        slug: "workspace-owner",
        name: "Workspace owner",
        description: null,
        scope_type: "workspace",
        scope_id: "workspace-1",
        permissions: ["Workspace.Settings.ReadWrite"],
        built_in: true,
        editable: false,
      },
    ];

    useWorkspaceMembersQueryMock.mockReturnValue({ data: [member], isLoading: false, error: null });
    useWorkspaceRolesQueryMock.mockReturnValue({ data: roles, isLoading: false, error: null });

    useOutletContextMock.mockReturnValue({ workspace: mockWorkspace });

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <WorkspaceMembersRoute />
      </QueryClientProvider>,
    );

    expect(screen.getByText(/user one/i)).toBeInTheDocument();
    expect(screen.getByText(/workspace owner/i)).toBeInTheDocument();
  });

  it("focuses the first interactive control when opening the add member dialog and restores focus", async () => {
    const user = userEvent.setup();
    useWorkspaceMembersQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });
    useWorkspaceRolesQueryMock.mockReturnValue({
      data: [
        {
          id: "role-1",
          slug: "workspace-owner",
          name: "Workspace owner",
          description: null,
          scope_type: "workspace",
          scope_id: "workspace-1",
          permissions: ["Workspace.Settings.ReadWrite"],
          built_in: true,
          editable: false,
        },
      ],
      isLoading: false,
      error: null,
    });

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <WorkspaceMembersRoute />
      </QueryClientProvider>,
    );

    const inviteButton = screen.getByRole("button", { name: /invite member/i });
    inviteButton.focus();

    await user.click(inviteButton);

    const userIdField = await screen.findByLabelText(/user id/i);
    expect(userIdField).toHaveFocus();

    await user.click(screen.getByRole("button", { name: /cancel/i }));

    await waitFor(() => {
      expect(inviteButton).toHaveFocus();
    });
  });
});

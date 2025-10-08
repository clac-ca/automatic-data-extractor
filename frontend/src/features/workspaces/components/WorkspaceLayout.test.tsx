import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { SessionEnvelope } from "../../../shared/api/types";

const useWorkspacesQueryMock = vi.fn();
const useSessionQueryMock = vi.fn();
const navigateMock = vi.fn();
const createWorkspaceMutationMock = { mutateAsync: vi.fn(), isPending: false };

vi.mock("../hooks/useWorkspacesQuery", () => ({
  useWorkspacesQuery: () => useWorkspacesQueryMock(),
}));

vi.mock("../../auth/hooks/useSessionQuery", () => ({
  useSessionQuery: () => useSessionQueryMock(),
}));

vi.mock("../hooks/useCreateWorkspaceMutation", () => ({
  useCreateWorkspaceMutation: () => createWorkspaceMutationMock,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");

  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => ({}),
    Outlet: () => null,
  };
});

import { WorkspaceLayout } from "./WorkspaceLayout";

describe("WorkspaceLayout", () => {
  beforeEach(() => {
    useWorkspacesQueryMock.mockReset();
    useSessionQueryMock.mockReset();
    navigateMock.mockReset();
    createWorkspaceMutationMock.mutateAsync.mockReset();
  });

  it("shows an actionable empty state for administrators with no workspaces", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      user: {
        user_id: "admin-1",
        email: "admin@example.com",
        role: "admin",
        is_active: true,
        is_service_account: false,
        display_name: "Admin User",
        preferred_workspace_id: null,
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(screen.getByText(/create your first workspace/i)).toBeInTheDocument();
    const createButton = screen.getByRole("button", { name: /create workspace/i });
    expect(createButton).toBeInTheDocument();

    await user.click(createButton);
    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByRole("dialog", { name: /create workspace/i })).not.toBeInTheDocument();
  });

  it("shows a restricted message when the user cannot create workspaces", () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        role: "user",
        is_active: true,
        is_service_account: false,
        display_name: "Regular User",
        preferred_workspace_id: null,
        permissions: [],
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(
      screen.getByText(/no workspaces are available for your account yet\. ask an administrator to grant access\./i),
    ).toBeInTheDocument();
  });

  it("allows permitted users to start workspace creation when no workspaces exist", () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        role: "user",
        is_active: true,
        is_service_account: false,
        display_name: "Regular User",
        preferred_workspace_id: null,
        permissions: ["workspaces:create"],
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(screen.getByRole("button", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("treats service accounts as read-only even if marked as admin", () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "service-1",
        email: "svc@example.com",
        role: "admin",
        is_active: true,
        is_service_account: true,
        preferred_workspace_id: null,
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(
      screen.getByText(/no workspaces are available for your account yet\. ask an administrator to grant access\./i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /create workspace/i })).not.toBeInTheDocument();
  });

  it("opens and closes the create workspace dialog from the top bar", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      user: {
        user_id: "admin-1",
        email: "admin@example.com",
        role: "admin",
        is_active: true,
        is_service_account: false,
        display_name: "Admin User",
        preferred_workspace_id: null,
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({
      data: [
        {
          id: "workspace-1",
          name: "Finance",
          slug: "finance",
          role: "owner",
          permissions: ["workspace:members:manage"],
          is_default: true,
        },
      ],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    expect(screen.queryByRole("dialog", { name: /create workspace/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /new workspace/i }));
    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByRole("dialog", { name: /create workspace/i })).not.toBeInTheDocument();
  });

  it("navigates when switching workspaces from the selector", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        role: "user",
        is_active: true,
        is_service_account: false,
        display_name: "Regular User",
        preferred_workspace_id: null,
        permissions: [],
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({
      data: [
        {
          id: "workspace-1",
          name: "Finance",
          slug: "finance",
          role: "owner",
          permissions: [],
          is_default: true,
        },
        {
          id: "workspace-2",
          name: "Operations",
          slug: "operations",
          role: "member",
          permissions: [],
          is_default: false,
        },
      ],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);
    navigateMock.mockClear();

    await user.selectOptions(screen.getByLabelText(/workspace/i), "workspace-2");

    expect(navigateMock).toHaveBeenCalledWith("/workspaces/workspace-2");
  });
});

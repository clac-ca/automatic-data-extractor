import { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { SessionEnvelope, WorkspaceProfile } from "../../../shared/api/types";

const useWorkspacesQueryMock = vi.fn();
const useSessionQueryMock = vi.fn();
const navigateMock = vi.fn();
const useParamsMock = vi.fn(() => ({}));

vi.mock("../hooks/useWorkspacesQuery", () => ({
  useWorkspacesQuery: () => useWorkspacesQueryMock(),
}));

vi.mock("../../auth/hooks/useSessionQuery", () => ({
  useSessionQuery: () => useSessionQueryMock(),
}));

vi.mock("../hooks/useCreateWorkspaceMutation", () => ({
  useCreateWorkspaceMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");

  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => useParamsMock(),
    useLocation: () => ({ pathname: "/workspaces", search: "", hash: "", state: null, key: "test" }),
    NavLink: ({ children, to }: { children: ReactNode; to: string }) => <a href={String(to)}>{children}</a>,
    Outlet: () => null,
  };
});

import { WorkspaceLayout } from "./WorkspaceLayout";

const baseSession: SessionEnvelope = {
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

const workspace = (overrides: Partial<WorkspaceProfile> = {}): WorkspaceProfile => ({
  id: "workspace-1",
  name: "Finance",
  slug: "finance",
  roles: ["workspace-owner"],
  permissions: ["Workspace.Members.Read", "Workspace.Documents.Read"],
  is_default: true,
  ...overrides,
});

describe("WorkspaceLayout", () => {
  beforeEach(() => {
    useWorkspacesQueryMock.mockReset();
    useSessionQueryMock.mockReset();
    navigateMock.mockReset();
    useParamsMock.mockReset();
    useParamsMock.mockReturnValue({});
  });

  it("shows an actionable empty state for users with workspace creation rights", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      ...baseSession,
      user: {
        ...baseSession.user,
        permissions: ["Workspaces.Create"],
      },
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(screen.getByText(/create your first workspace/i)).toBeInTheDocument();
    const createButton = screen.getByRole("button", { name: /create workspace/i });
    await user.click(createButton);
    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("shows a restricted message when the user cannot create workspaces", () => {
    useSessionQueryMock.mockReturnValue({ data: baseSession, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(
      screen.getByText(/no workspaces are available for your account yet\. ask an administrator to grant access\./i),
    ).toBeInTheDocument();
  });

  it("hides workspace creation for service accounts", () => {
    const session: SessionEnvelope = {
      ...baseSession,
      user: {
        ...baseSession.user,
        is_service_account: true,
        permissions: ["Workspaces.Create"],
      },
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(screen.queryByRole("button", { name: /create workspace/i })).not.toBeInTheDocument();
  });

  it("opens the dialog from the top bar for eligible users", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      ...baseSession,
      user: {
        ...baseSession.user,
        permissions: ["Workspaces.Create"],
      },
    };
    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace()],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    await user.click(screen.getByRole("button", { name: /new workspace/i }));
    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("navigates when switching workspaces from the selector", async () => {
    const user = userEvent.setup();
    useSessionQueryMock.mockReturnValue({ data: baseSession, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({
      data: [
        workspace({ id: "workspace-1", name: "Finance", roles: ["workspace-owner"] }),
        workspace({ id: "workspace-2", name: "Operations", slug: "operations", roles: ["workspace-member"], is_default: false }),
      ],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    await user.selectOptions(screen.getByLabelText(/workspace/i), "workspace-2");

    expect(navigateMock).toHaveBeenCalledWith("/workspaces/workspace-2");
  });

  it("redirects to the workspace list when the route workspace is unknown", () => {
    useSessionQueryMock.mockReturnValue({ data: baseSession, isLoading: false, error: null });
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace({ id: "workspace-1" })],
      isLoading: false,
      error: null,
    });
    useParamsMock.mockReturnValue({ workspaceId: "missing-workspace" });

    render(<WorkspaceLayout />);

    expect(navigateMock).toHaveBeenCalledWith("/workspaces", { replace: true });
  });
});

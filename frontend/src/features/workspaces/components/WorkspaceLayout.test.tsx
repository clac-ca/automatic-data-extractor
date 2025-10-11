import { type ReactNode } from "react";
import type { Location } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { SessionEnvelope, WorkspaceProfile } from "../../../shared/api/types";

const useWorkspacesQueryMock = vi.fn();
const navigateMock = vi.fn();
const useParamsMock = vi.fn(() => ({}));
const locationMock: Location = {
  pathname: "/workspaces",
  search: "",
  hash: "",
  state: null,
  key: "initial",
};

const baseSession: SessionEnvelope = {
  user: {
    user_id: "user-1",
    email: "user@example.com",
    is_active: true,
    is_service_account: false,
    display_name: "Regular User",
    preferred_workspace_id: null,
    roles: ["global-user"],
    permissions: [],
  },
  expires_at: new Date().toISOString(),
  refresh_expires_at: new Date().toISOString(),
};

const sessionContextRef: { current: SessionEnvelope } = { current: baseSession };

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    } satisfies MediaQueryList)),
  });
});

vi.mock("../hooks/useWorkspacesQuery", () => ({
  useWorkspacesQuery: () => useWorkspacesQueryMock(),
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
    useLocation: () => locationMock,
    useOutletContext: () => sessionContextRef.current,
    NavLink: ({ children, to }: { children: ReactNode; to: string }) => <a href={String(to)}>{children}</a>,
    Outlet: () => null,
  };
});

import { WorkspaceLayout } from "./WorkspaceLayout";

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
    navigateMock.mockReset();
    useParamsMock.mockReset();
    useParamsMock.mockReturnValue({});
    sessionContextRef.current = baseSession;
    Object.assign(locationMock, {
      pathname: "/workspaces",
      search: "",
      hash: "",
      state: null,
      key: "test",
    });
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
    sessionContextRef.current = session;
    useWorkspacesQueryMock.mockReturnValue({ data: [], isLoading: false, error: null });

    render(<WorkspaceLayout />);

    expect(screen.getByText(/create your first workspace/i)).toBeInTheDocument();
    const canvas = screen.getByRole("main");
    const createButton = within(canvas).getByRole("button", { name: /create workspace/i });
    await user.click(createButton);
    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("shows a restricted message when the user cannot create workspaces", () => {
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
    sessionContextRef.current = session;
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
    sessionContextRef.current = session;
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace()],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    const topBar = screen.getByRole("banner", { name: /workspace chrome header/i });
    await user.click(within(topBar).getByRole("button", { name: /new workspace/i }));
    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("opens the dialog from the workspace rail action", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      ...baseSession,
      user: {
        ...baseSession.user,
        permissions: ["Workspaces.Create"],
      },
    };
    sessionContextRef.current = session;
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace({ id: "workspace-1", name: "Finance" })],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    const navigation = screen.getByLabelText("Workspace navigation");
    await user.click(within(navigation).getByRole("button", { name: /new workspace/i }));

    expect(screen.getByRole("dialog", { name: /create workspace/i })).toBeInTheDocument();
  });

  it("retains a discoverable create action when the rail is collapsed", async () => {
    const user = userEvent.setup();
    const session: SessionEnvelope = {
      ...baseSession,
      user: {
        ...baseSession.user,
        permissions: ["Workspaces.Create"],
      },
    };
    sessionContextRef.current = session;
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace({ id: "workspace-1", name: "Finance" })],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    const topBar = screen.getByRole("banner", { name: /workspace chrome header/i });
    await user.click(within(topBar).getByRole("button", { name: /collapse navigation/i }));

    const navigation = screen.getByLabelText("Workspace navigation");
    const createAction = within(navigation).getByRole("button", { name: /new workspace/i });

    expect(createAction).toBeInTheDocument();
  });

  it("navigates when switching workspaces from the selector", async () => {
    const user = userEvent.setup();
    useParamsMock.mockReturnValue({ workspaceId: "workspace-1" });
    Object.assign(locationMock, {
      pathname: "/workspaces/workspace-1/documents",
      search: "?page=2",
      hash: "#section",
    });
    useWorkspacesQueryMock.mockReturnValue({
      data: [
        workspace({ id: "workspace-1", name: "Finance", roles: ["workspace-owner"] }),
        workspace({ id: "workspace-2", name: "Operations", slug: "operations", roles: ["workspace-member"], is_default: false }),
      ],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    await user.selectOptions(screen.getByRole("combobox", { name: /workspace/i }), "workspace-2");

    expect(navigateMock).toHaveBeenCalledWith("/workspaces/workspace-2/documents?page=2#section");
  });

  it("builds workspace navigation links using absolute paths", () => {
    useParamsMock.mockReturnValue({ workspaceId: "workspace-1" });
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace({ id: "workspace-1", permissions: ["Workspace.Documents.Read"] })],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    const documentsLink = within(screen.getByRole("main")).getByRole("link", { name: /documents/i });
    expect(documentsLink).toHaveAttribute("href", "/workspaces/workspace-1/documents");
  });

  it("hides the workspace navigation when only overview is available", () => {
    useParamsMock.mockReturnValue({ workspaceId: "workspace-1" });
    useWorkspacesQueryMock.mockReturnValue({
      data: [workspace({ id: "workspace-1", permissions: [] })],
      isLoading: false,
      error: null,
    });

    render(<WorkspaceLayout />);

    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("redirects to the workspace list when the route workspace is unknown", () => {
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

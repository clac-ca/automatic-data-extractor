import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen } from "@test/test-utils";
import { useSession } from "../../context/SessionContext";
import { RequireSession } from "../RequireSession";
import type { SessionEnvelope } from "../../api";

const mockUseSessionQuery = vi.fn();
const mockUseSetupStatusQuery = vi.fn();

vi.mock("../../hooks/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

vi.mock("../../hooks/useSetupStatusQuery", () => ({
  useSetupStatusQuery: (enabled?: boolean) => mockUseSetupStatusQuery(enabled),
}));

describe("RequireSession", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
    mockUseSetupStatusQuery.mockReset();

    mockUseSetupStatusQuery.mockReturnValue({
      data: { requires_setup: false },
      isPending: false,
      isSuccess: true,
      isError: false,
      refetch: vi.fn(),
    });
  });

  it("renders a loading state while the session is being fetched", () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });

    render(
      <RouterProvider
        router={createMemoryRouter([
          { path: "/", element: <RequireSession>Loading test</RequireSession> },
        ])}
      />,
    );

    expect(screen.getByText("Loading your workspace…")).toBeInTheDocument();
  });

  it("allows retrying when the session request fails", async () => {
    const refetch = vi.fn();
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: true,
      refetch,
    });

    render(
      <RouterProvider
        router={createMemoryRouter([
          { path: "/", element: <RequireSession>Error state</RequireSession> },
        ])}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(refetch).toHaveBeenCalled();
  });

  it("redirects to the login screen when no session is present", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    mockUseSetupStatusQuery.mockReturnValue({
      data: { requires_setup: false },
      isPending: false,
      isSuccess: true,
      isError: false,
      refetch: vi.fn(),
    });

    const router = createMemoryRouter(
      [
        { path: "/login", element: <div>Login screen</div> },
        {
          path: "/workspaces",
          element: <RequireSession>Protected</RequireSession>,
        },
      ],
      { initialEntries: ["/workspaces"] },
    );

    render(<RouterProvider router={router} />);

    await screen.findByText("Login screen");
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("");
    expect(router.state.location.state).toBeNull();
  });

  it("redirects to the setup screen when initial setup is required", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    mockUseSetupStatusQuery.mockReturnValue({
      data: { requires_setup: true },
      isPending: false,
      isSuccess: true,
      isError: false,
      refetch: vi.fn(),
    });

    const router = createMemoryRouter(
      [
        { path: "/setup", element: <div>Setup screen</div> },
        {
          path: "/workspaces",
          element: <RequireSession>Protected</RequireSession>,
        },
      ],
      { initialEntries: ["/workspaces"] },
    );

    render(<RouterProvider router={router} />);

    await screen.findByText("Setup screen");
    expect(router.state.location.pathname).toBe("/setup");
  });

  it("preserves the redirect path for non-default routes", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    const router = createMemoryRouter(
      [
        { path: "/login", element: <div>Login screen</div> },
        {
          path: "/workspaces/alpha",
          element: <RequireSession>Protected</RequireSession>,
        },
      ],
      { initialEntries: ["/workspaces/alpha"] },
    );

    render(<RouterProvider router={router} />);

    await screen.findByText("Login screen");
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("?redirectTo=%2Fworkspaces%2Falpha");
  });

  it("allows retrying when setup status fails to load", async () => {
    const refetch = vi.fn();
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    mockUseSetupStatusQuery.mockReturnValue({
      isError: true,
      isPending: false,
      isSuccess: false,
      data: undefined,
      refetch,
    });

    render(
      <RouterProvider
        router={createMemoryRouter([
          { path: "/", element: <RequireSession>Error state</RequireSession> },
        ])}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(refetch).toHaveBeenCalled();
  });

  it("renders children when a session is available and provides session context", async () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "user@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Test User",
        permissions: ["Workspaces.Create"],
      },
      expires_at: new Date(Date.now() + 120_000).toISOString(),
      refresh_expires_at: new Date(Date.now() + 300_000).toISOString(),
      return_to: null,
    };

    mockUseSessionQuery.mockReturnValue({
      session,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    function SessionConsumer() {
      const activeSession = useSession();
      return <p>Signed in as {activeSession.user.display_name}</p>;
    }

    render(
      <RouterProvider
        router={createMemoryRouter([
          {
            path: "/",
            element: (
              <RequireSession>
                <SessionConsumer />
              </RequireSession>
            ),
          },
        ])}
      />,
    );

    expect(await screen.findByText("Signed in as Test User")).toBeInTheDocument();
  });
});

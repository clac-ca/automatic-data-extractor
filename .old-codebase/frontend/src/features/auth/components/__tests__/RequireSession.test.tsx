import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, beforeEach, vi } from "vitest";

import { render, screen } from "../../../../test/test-utils";
import type { SessionEnvelope } from "@shared/types/auth";
import { useSession } from "../../context/SessionContext";
import { RequireSession } from "../RequireSession";

const mockUseSessionQuery = vi.fn();

vi.mock("../../hooks/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

describe("RequireSession", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
  });

  it("renders a loading state while the session is being fetched", () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: true,
      error: null,
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
      error: new Error("boom"),
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
      error: null,
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
      error: null,
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

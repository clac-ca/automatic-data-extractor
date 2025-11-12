import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NavProvider } from "@app/nav/history";
import { render, screen, waitFor } from "@test/test-utils";
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

function renderWithNav(ui: React.ReactElement, path = "/") {
  window.history.replaceState(null, "", path);
  return render(<NavProvider>{ui}</NavProvider>);
}

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

    renderWithNav(<RequireSession>Loading test</RequireSession>);

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

    renderWithNav(<RequireSession>Error state</RequireSession>);

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

    renderWithNav(<RequireSession>Protected</RequireSession>, "/workspaces");

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(window.location.search).toBe("");
  });

  it("redirects to the setup screen when initial setup is required", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    mockUseSetupStatusQuery.mockReturnValue({
      data: { requires_setup: true, force_sso: false },
      isPending: false,
      isSuccess: true,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithNav(<RequireSession>Protected</RequireSession>, "/workspaces");

    await waitFor(() => expect(window.location.pathname).toBe("/setup"));
  });

  it("preserves the redirect path for non-default routes", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithNav(<RequireSession>Protected</RequireSession>, "/workspaces/alpha");

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(window.location.search).toBe("?redirectTo=%2Fworkspaces%2Falpha");
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

    renderWithNav(<RequireSession>Error state</RequireSession>);

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

    renderWithNav(
      <RequireSession>
        <SessionConsumer />
      </RequireSession>,
    );

    expect(await screen.findByText("Signed in as Test User")).toBeInTheDocument();
  });
});

import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { render, screen, waitFor } from "@test/test-utils";
import { RequireSession } from "@components/auth/RequireSession";
import { useSession } from "@components/auth/SessionContext";
import type { SessionEnvelope } from "@api/auth/api";

const mockUseSessionQuery = vi.fn();
const mockUseSetupStatusQuery = vi.fn();

vi.mock("@hooks/auth/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

vi.mock("@hooks/auth/useSetupStatusQuery", () => ({
  useSetupStatusQuery: (enabled?: boolean) => mockUseSetupStatusQuery(enabled),
}));

function renderWithHistory(ui: React.ReactElement, path = "/") {
  window.history.replaceState(null, "", path);
  return render(ui);
}

describe("RequireSession", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
    mockUseSetupStatusQuery.mockReset();

    mockUseSetupStatusQuery.mockReturnValue({
      data: {
        setup_required: false,
        registration_mode: "closed",
        oidc_configured: false,
        providers: [],
      },
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

    renderWithHistory(<RequireSession>Loading test</RequireSession>);

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

    renderWithHistory(<RequireSession>Error state</RequireSession>);

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

    renderWithHistory(<RequireSession>Protected</RequireSession>, "/workspaces");

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
      data: {
        setup_required: true,
        registration_mode: "setup-only",
        oidc_configured: false,
        providers: [],
      },
      isPending: false,
      isSuccess: true,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithHistory(<RequireSession>Protected</RequireSession>, "/workspaces");

    await waitFor(() => expect(window.location.pathname).toBe("/setup"));
  });

  it("preserves the redirect path for non-default routes", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithHistory(<RequireSession>Protected</RequireSession>, "/workspaces/alpha");

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

    renderWithHistory(<RequireSession>Error state</RequireSession>);

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(refetch).toHaveBeenCalled();
  });

  it("renders children when a session is available and provides session context", async () => {
    const session: SessionEnvelope = {
      user: {
        id: "user-1",
        email: "user@example.com",
        is_service_account: false,
        display_name: "Test User",
        roles: [],
        permissions: ["workspaces.create"],
        preferred_workspace_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      workspaces: {
        items: [],
        page: 1,
        page_size: 50,
        total: 0,
        has_next: false,
        has_previous: false,
      },
      roles: [],
      permissions: ["workspaces.create"],
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

    renderWithHistory(
      <RequireSession>
        <SessionConsumer />
      </RequireSession>,
    );

    expect(await screen.findByText("Signed in as Test User")).toBeInTheDocument();
  });
});

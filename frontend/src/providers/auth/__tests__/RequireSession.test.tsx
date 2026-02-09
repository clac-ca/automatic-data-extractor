import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { render as rtlRender, screen, waitFor } from "@testing-library/react";
import { AllProviders } from "@/test/test-utils";
import { RequireSession } from "@/providers/auth/RequireSession";
import { useSession } from "@/providers/auth/SessionContext";
import type { SessionEnvelope } from "@/api/auth/api";

const mockUseSessionQuery = vi.fn();
const mockUseSetupStatusQuery = vi.fn();
const mockUseMfaStatusQuery = vi.fn();

vi.mock("@/hooks/auth/useSessionQuery", () => ({
  useSessionQuery: () => mockUseSessionQuery(),
}));

vi.mock("@/hooks/auth/useSetupStatusQuery", () => ({
  useSetupStatusQuery: (enabled?: boolean) => mockUseSetupStatusQuery(enabled),
}));

vi.mock("@/hooks/auth/useMfaStatusQuery", () => ({
  useMfaStatusQuery: (options?: { enabled?: boolean }) => mockUseMfaStatusQuery(options),
}));

function LocationDisplay() {
  const location = useLocation();
  return <span data-testid="location">{`${location.pathname}${location.search}`}</span>;
}

function RouteShell({ children }: { readonly children: React.ReactNode }) {
  return (
    <AllProviders>
      <LocationDisplay />
      {children}
    </AllProviders>
  );
}

function renderWithHistory(ui: React.ReactElement, path = "/") {
  return rtlRender(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<RouteShell>Login</RouteShell>} />
        <Route path="/setup" element={<RouteShell>Setup</RouteShell>} />
        <Route path="*" element={<RouteShell>{ui}</RouteShell>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireSession", () => {
  beforeEach(() => {
    mockUseSessionQuery.mockReset();
    mockUseSetupStatusQuery.mockReset();
    mockUseMfaStatusQuery.mockReset();

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

    mockUseMfaStatusQuery.mockReturnValue({
      data: {
        enabled: false,
        enrolledAt: null,
        recoveryCodesRemaining: null,
        onboardingRecommended: false,
        onboardingRequired: false,
        skipAllowed: false,
      },
      isPending: false,
      isError: false,
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

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/login?returnTo=%2Fworkspaces"));
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

    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/setup?returnTo=%2Fworkspaces"));
  });

  it("preserves the redirect path for non-default routes", async () => {
    mockUseSessionQuery.mockReturnValue({
      session: null,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderWithHistory(<RequireSession>Protected</RequireSession>, "/workspaces/alpha");

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/login?returnTo=%2Fworkspaces%2Falpha"),
    );
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
      workspaces: [],
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

  it("redirects authenticated users to MFA setup when onboarding is required", async () => {
    const session: SessionEnvelope = {
      user: {
        id: "user-1",
        email: "user@example.com",
        is_service_account: false,
        display_name: "Test User",
        roles: [],
        permissions: [],
        preferred_workspace_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      workspaces: [],
      roles: [],
      permissions: [],
      return_to: null,
    };

    mockUseSessionQuery.mockReturnValue({
      session,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    mockUseMfaStatusQuery.mockReturnValue({
      data: {
        enabled: false,
        enrolledAt: null,
        recoveryCodesRemaining: null,
        onboardingRecommended: false,
        onboardingRequired: true,
        skipAllowed: false,
      },
      isPending: false,
      isError: false,
    });

    renderWithHistory(<RequireSession>Protected</RequireSession>, "/workspaces");

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/mfa/setup?returnTo=%2Fworkspaces"),
    );
  });
});

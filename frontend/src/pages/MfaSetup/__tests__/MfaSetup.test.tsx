import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { render as rtlRender, screen, waitFor } from "@testing-library/react";
import type { MfaStatusResponse } from "@/api/auth/api";
import { AllProviders } from "@/test/test-utils";
import MfaSetupPage from "@/pages/MfaSetup";

const mockFetchMfaStatus = vi.fn();

vi.mock("@/api/auth/api", async () => {
  const actual = await vi.importActual<typeof import("@/api/auth/api")>("@/api/auth/api");
  return {
    ...actual,
    fetchMfaStatus: (...args: unknown[]) => mockFetchMfaStatus(...args),
  };
});

vi.mock("@/features/mfa-setup", () => ({
  MfaSetupFlow: ({
    onRefreshMfaStatus,
    onFlowComplete,
  }: {
    readonly onRefreshMfaStatus: () => Promise<void>;
    readonly onFlowComplete?: () => void;
  }) => (
    <div data-testid="mfa-setup-flow">
      <button type="button" onClick={() => void onRefreshMfaStatus()}>
        Refresh status
      </button>
      <button type="button" onClick={() => onFlowComplete?.()}>
        Complete flow
      </button>
    </div>
  ),
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

function renderWithHistory(path = "/mfa/setup") {
  return rtlRender(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/workspaces" element={<RouteShell>Workspaces</RouteShell>} />
        <Route path="/mfa/setup" element={<RouteShell><MfaSetupPage /></RouteShell>} />
      </Routes>
    </MemoryRouter>,
  );
}

const REQUIRED_ONBOARDING_STATUS: MfaStatusResponse = {
  enabled: false,
  enrolledAt: null,
  recoveryCodesRemaining: null,
  onboardingRecommended: false,
  onboardingRequired: true,
  skipAllowed: false,
};

const ENABLED_STATUS: MfaStatusResponse = {
  enabled: true,
  enrolledAt: "2026-01-01T00:00:00Z",
  recoveryCodesRemaining: 10,
  onboardingRecommended: false,
  onboardingRequired: false,
  skipAllowed: false,
};

describe("MfaSetupPage", () => {
  beforeEach(() => {
    mockFetchMfaStatus.mockReset();
  });

  it("stays on setup after enrollment verification until the flow is explicitly completed", async () => {
    mockFetchMfaStatus
      .mockResolvedValueOnce(REQUIRED_ONBOARDING_STATUS)
      .mockResolvedValueOnce(ENABLED_STATUS);

    const user = userEvent.setup();
    renderWithHistory("/mfa/setup?returnTo=/workspaces");

    await screen.findByTestId("mfa-setup-flow");
    expect(screen.getByTestId("location")).toHaveTextContent("/mfa/setup?returnTo=/workspaces");

    await user.click(screen.getByRole("button", { name: "Refresh status" }));
    await waitFor(() => expect(mockFetchMfaStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("location")).toHaveTextContent("/mfa/setup?returnTo=/workspaces");

    await user.click(screen.getByRole("button", { name: "Complete flow" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/workspaces"));
  });
});

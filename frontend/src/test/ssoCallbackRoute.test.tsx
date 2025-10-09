import { describe, expect, it, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SsoCallbackRoute } from "../features/auth/routes/SsoCallbackRoute";
import { sessionKeys } from "../features/auth/hooks/sessionKeys";
import type { SessionEnvelope } from "../shared/api/types";

const getMock = vi.fn();

vi.mock("../shared/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../shared/api/client")>();
  return {
    ...actual,
    get: (...args: Parameters<typeof actual.get>) => getMock(...args),
  };
});

function renderCallback(initialEntry: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/auth/callback" element={<SsoCallbackRoute />} />
          <Route path="/documents" element={<div>Documents</div>} />
          <Route path="/workspaces" element={<div>Workspaces</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  return { ...view, client };
}

describe("SsoCallbackRoute", () => {
  beforeEach(() => {
    getMock.mockReset();
  });

  it("surfaces identity provider errors", async () => {
    renderCallback("/auth/callback?error=access_denied&error_description=Denied by policy");

    expect(
      await screen.findByText(/denied by policy/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /return to sign-in/i })).toBeInTheDocument();
    expect(getMock).not.toHaveBeenCalled();
  });

  it("exchanges the authorization code and redirects", async () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "ada@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Ada Lovelace",
        preferred_workspace_id: null,
        roles: ["global-user"],
        permissions: [],
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
      return_to: "/documents",
    };
    getMock.mockResolvedValueOnce(session);

    const { client } = renderCallback("/auth/callback?code=abc&state=xyz");

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith("/auth/sso/callback?code=abc&state=xyz");
    });

    expect(await screen.findByText(/documents/i)).toBeInTheDocument();
    expect(client.getQueryData(sessionKeys.detail())).toEqual(session);
  });
});

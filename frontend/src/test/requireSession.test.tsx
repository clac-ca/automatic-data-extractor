import { describe, expect, it, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import { RequireSession } from "../features/auth/components/RequireSession";

const useSessionQueryMock = vi.fn();

vi.mock("../features/auth/hooks/useSessionQuery", () => ({
  useSessionQuery: () => useSessionQueryMock(),
}));

describe("RequireSession", () => {
  beforeEach(() => {
    useSessionQueryMock.mockReset();
  });

  it("redirects to login when no session exists", () => {
    useSessionQueryMock.mockReturnValue({ data: null, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={["/workspaces"]}>
        <Routes>
          <Route path="/login" element={<div>Login</div>} />
          <Route element={<RequireSession />}>
            <Route path="/workspaces" element={<div>Workspaces</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/login/i)).toBeInTheDocument();
  });

  it("renders child routes when session is present", () => {
    useSessionQueryMock.mockReturnValue({
      data: {
        user: {
          user_id: "user-1",
          email: "ada@example.com",
          preferred_workspace_id: "workspace-1",
          display_name: "Ada Lovelace",
          is_active: true,
          is_service_account: false,
          roles: ["global-user"],
          permissions: [],
        },
        expires_at: new Date().toISOString(),
        refresh_expires_at: new Date().toISOString(),
      },
      isLoading: false,
      error: null,
    });

    render(
      <MemoryRouter initialEntries={["/workspaces"]}>
        <Routes>
          <Route element={<RequireSession />}>
            <Route path="/workspaces" element={<div>Protected content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/protected content/i)).toBeInTheDocument();
  });
});

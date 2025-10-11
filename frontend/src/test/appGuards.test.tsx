import { beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes, useOutletContext } from "react-router-dom";
import { render, screen } from "@testing-library/react";

import { RequireNoSession, RequireSession, RequireSetupComplete, RequireSetupIncomplete } from "../app/guards";
import type { SessionEnvelope, SetupStatusResponse } from "../shared/api/types";

const useSessionQueryMock = vi.fn();
const useOptionalSessionMock = vi.fn();
const useSetupStatusQueryMock = vi.fn();

vi.mock("../features/auth/hooks/useSessionQuery", () => ({
  useSessionQuery: () => useSessionQueryMock(),
}));

vi.mock("../features/auth/hooks/useOptionalSession", () => ({
  useOptionalSession: () => useOptionalSessionMock(),
}));

vi.mock("../features/setup/hooks/useSetupStatusQuery", () => ({
  useSetupStatusQuery: () => useSetupStatusQueryMock(),
}));

describe("RequireSession", () => {
  beforeEach(() => {
    useSessionQueryMock.mockReset();
  });

  it("redirects to login with return_to when session is missing", () => {
    useSessionQueryMock.mockReturnValue({ data: null, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={["/workspaces/alpha?tab=overview"]}>
        <Routes>
          <Route path="/login" element={<div>Login</div>} />
          <Route element={<RequireSession />}>
            <Route path="/workspaces/:workspaceId" element={<div>Workspace</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/login/i)).toBeInTheDocument();
  });

  it("renders child routes when session is present", () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "ada@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Ada Lovelace",
        preferred_workspace_id: "workspace-1",
        roles: ["global-user"],
        permissions: [],
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
    };

    useSessionQueryMock.mockReturnValue({ data: session, isLoading: false, error: null });

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

describe("RequireNoSession", () => {
  beforeEach(() => {
    useOptionalSessionMock.mockReset();
  });

  it("renders outlet when session is absent", () => {
    useOptionalSessionMock.mockReturnValue({ data: null, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route element={<RequireNoSession />}>
            <Route path="/login" element={<div>Login form</div>} />
          </Route>
          <Route path="/workspaces" element={<div>Workspaces</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/login form/i)).toBeInTheDocument();
  });

  it("redirects to preferred workspace when session exists", () => {
    const session: SessionEnvelope = {
      user: {
        user_id: "user-1",
        email: "ada@example.com",
        is_active: true,
        is_service_account: false,
        display_name: "Ada Lovelace",
        preferred_workspace_id: "workspace-42",
      },
      expires_at: new Date().toISOString(),
      refresh_expires_at: new Date().toISOString(),
      return_to: null,
    };

    useOptionalSessionMock.mockReturnValue({ data: session, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route element={<RequireNoSession />}>
            <Route path="/login" element={<div>Login form</div>} />
          </Route>
          <Route path="/workspaces/:workspaceId" element={<div>Workspace landing</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/workspace landing/i)).toBeInTheDocument();
  });
});

describe("RequireSetupComplete", () => {
  beforeEach(() => {
    useSetupStatusQueryMock.mockReset();
  });

  it("redirects to setup when provisioning is still required", () => {
    const status: SetupStatusResponse = {
      requires_setup: true,
      completed_at: null,
      force_sso: false,
    };

    useSetupStatusQueryMock.mockReturnValue({ data: status, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/setup" element={<div>Setup wizard</div>} />
          <Route element={<RequireSetupComplete />}>
            <Route path="/login" element={<div>Login form</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/setup wizard/i)).toBeInTheDocument();
  });
});

describe("RequireSetupIncomplete", () => {
  beforeEach(() => {
    useSetupStatusQueryMock.mockReset();
  });

  it("redirects to login when setup is complete", () => {
    const status: SetupStatusResponse = {
      requires_setup: false,
      completed_at: new Date().toISOString(),
      force_sso: false,
    };

    useSetupStatusQueryMock.mockReturnValue({ data: status, isLoading: false, error: null });

    render(
      <MemoryRouter initialEntries={["/setup"]}>
        <Routes>
          <Route path="/login" element={<div>Login screen</div>} />
          <Route element={<RequireSetupIncomplete />}>
            <Route path="/setup" element={<div>Setup route</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/login screen/i)).toBeInTheDocument();
  });

  it("provides setup status context to children", () => {
    const status: SetupStatusResponse = {
      requires_setup: true,
      completed_at: null,
      force_sso: true,
    };

    useSetupStatusQueryMock.mockReturnValue({ data: status, isLoading: false, error: null });

    function Consumer() {
      const context = useOutletContext<SetupStatusResponse>();
      return (
        <div>
          Setup pending: {context.requires_setup ? "yes" : "no"}, force SSO: {context.force_sso ? "yes" : "no"}
        </div>
      );
    }

    render(
      <MemoryRouter initialEntries={["/setup"]}>
        <Routes>
          <Route element={<RequireSetupIncomplete />}>
            <Route path="/setup" element={<Consumer />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/setup pending: yes/i)).toBeInTheDocument();
    expect(screen.getByText(/force sso: yes/i)).toBeInTheDocument();
  });
});

import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { appRoutes } from "@/app/routes";

vi.mock("@/pages/Home", () => ({ default: () => <div data-testid="home-screen">home</div> }));
vi.mock("@/pages/ForgotPassword", () => ({ default: () => <div data-testid="forgot-password-screen">forgot-password</div> }));
vi.mock("@/pages/Account", () => ({ default: () => <div data-testid="account-screen">account</div> }));
vi.mock("@/pages/Login", () => ({ default: () => <div data-testid="login-screen">login</div> }));
vi.mock("@/pages/MfaSetup", () => ({ default: () => <div data-testid="mfa-setup-screen">mfa-setup</div> }));
vi.mock("@/pages/Setup", () => ({ default: () => <div data-testid="setup-screen">setup</div> }));
vi.mock("@/pages/OrganizationSettings", () => ({ default: () => <div data-testid="org-settings-screen">org-settings</div> }));
vi.mock("@/pages/ResetPassword", () => ({ default: () => <div data-testid="reset-password-screen">reset-password</div> }));
vi.mock("@/pages/Workspaces", () => ({ default: () => <div data-testid="workspaces-screen">workspaces</div> }));
vi.mock("@/pages/Workspaces/New", () => ({ default: () => <div data-testid="workspace-new-screen">new</div> }));
vi.mock("@/pages/Workspace", () => ({ default: () => <div data-testid="workspace-screen">workspace</div> }));
vi.mock("@/pages/Logout", () => ({ default: () => <div data-testid="logout-screen">logout</div> }));
vi.mock("@/pages/NotFound", () => ({ default: () => <div data-testid="not-found-screen">not-found</div> }));
vi.mock("@/providers/auth/RequireSession", () => ({
  RequireSession: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock("@/providers/auth/SessionContext", () => ({
  useSession: () => ({
    user: {
      display_name: "Test User",
      email: "test@example.com",
    },
  }),
}));

function renderAt(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
}

describe("App routes", () => {
  const cases: Array<{ path: string; testId: string }> = [
    { path: "/", testId: "home-screen" },
    { path: "/forgot-password", testId: "forgot-password-screen" },
    { path: "/account", testId: "account-screen" },
    { path: "/account/security", testId: "account-screen" },
    { path: "/account/profile", testId: "account-screen" },
    { path: "/account/api-keys", testId: "account-screen" },
    { path: "/login", testId: "login-screen" },
    { path: "/mfa/setup", testId: "mfa-setup-screen" },
    { path: "/reset-password", testId: "reset-password-screen" },
    { path: "/setup", testId: "setup-screen" },
    { path: "/organization", testId: "org-settings-screen" },
    { path: "/organization/users", testId: "org-settings-screen" },
    { path: "/workspaces", testId: "workspaces-screen" },
    { path: "/workspaces/new", testId: "workspace-new-screen" },
    { path: "/workspaces/ws-1", testId: "workspace-screen" },
    { path: "/workspaces/ws-1/config-builder", testId: "workspace-screen" },
    { path: "/workspaces/ws-1/config-builder/cfg-1/editor", testId: "workspace-screen" },
  ];

  for (const { path, testId } of cases) {
    it(`renders ${path}`, async () => {
      renderAt(path);
      expect(await screen.findByTestId(testId)).toBeInTheDocument();
    });
  }

  it("falls back to the not found screen", async () => {
    renderAt("/missing/path");
    expect(await screen.findByTestId("not-found-screen")).toBeInTheDocument();
  });
});

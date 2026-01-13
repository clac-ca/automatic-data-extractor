import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { appRoutes } from "../routes";
import { normalizePathname } from "@app/navigation/paths";

vi.mock("@pages/Home", () => ({ default: () => <div data-testid="home-screen">home</div> }));
vi.mock("@pages/Login", () => ({ default: () => <div data-testid="login-screen">login</div> }));
vi.mock("@pages/Setup", () => ({ default: () => <div data-testid="setup-screen">setup</div> }));
vi.mock("@pages/Workspaces", () => ({ default: () => <div data-testid="workspaces-screen">workspaces</div> }));
vi.mock("@pages/Workspaces/New", () => ({ default: () => <div data-testid="workspace-new-screen">new</div> }));
vi.mock("@pages/Workspace", () => ({ default: () => <div data-testid="workspace-screen">workspace</div> }));
vi.mock("@pages/Logout", () => ({ default: () => <div data-testid="logout-screen">logout</div> }));
vi.mock("@pages/NotFound", () => ({ default: () => <div data-testid="not-found-screen">not-found</div> }));
vi.mock("@components/providers/auth/RequireSession", () => ({
  RequireSession: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

function renderAt(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
}

describe("normalizePathname", () => {
  it("normalizes empty or trailing slash paths", () => {
    expect(normalizePathname("")).toBe("/");
    expect(normalizePathname("/")).toBe("/");
    expect(normalizePathname("/workspaces/")).toBe("/workspaces");
    expect(normalizePathname("/workspaces/abc/")).toBe("/workspaces/abc");
  });
});

describe("App routes", () => {
  const cases: Array<{ path: string; testId: string }> = [
    { path: "/", testId: "home-screen" },
    { path: "/login", testId: "login-screen" },
    { path: "/setup", testId: "setup-screen" },
    { path: "/workspaces", testId: "workspaces-screen" },
    { path: "/workspaces/new", testId: "workspace-new-screen" },
    { path: "/workspaces/ws-1", testId: "workspace-screen" },
    { path: "/workspaces/ws-1/config-builder", testId: "workspace-screen" },
    { path: "/workspaces/ws-1/config-builder/cfg-1/editor", testId: "workspace-screen" },
  ];

  for (const { path, testId } of cases) {
    it(`renders ${path}`, () => {
      renderAt(path);
      expect(screen.getByTestId(testId)).toBeInTheDocument();
    });
  }

  it("falls back to the not found screen", () => {
    renderAt("/missing/path");
    expect(screen.getByTestId("not-found-screen")).toBeInTheDocument();
  });
});

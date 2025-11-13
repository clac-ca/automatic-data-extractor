import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@test/test-utils";

import { ScreenSwitch, normalizePathname } from "../App";

vi.mock("@screens/Home", () => ({ default: () => <div data-testid="home-screen">home</div> }));
vi.mock("@screens/Login", () => ({ default: () => <div data-testid="login-screen">login</div> }));
vi.mock("@screens/AuthCallback", () => ({ default: () => <div data-testid="auth-callback-screen">auth</div> }));
vi.mock("@screens/Setup", () => ({ default: () => <div data-testid="setup-screen">setup</div> }));
vi.mock("@screens/Workspaces", () => ({ default: () => <div data-testid="workspaces-screen">workspaces</div> }));
vi.mock("@screens/Workspaces/New", () => ({ default: () => <div data-testid="workspace-new-screen">new</div> }));
vi.mock("@screens/Workspace", () => ({ default: () => <div data-testid="workspace-screen">workspace</div> }));
vi.mock("@screens/Logout", () => ({ default: () => <div data-testid="logout-screen">logout</div> }));
vi.mock("@screens/NotFound", () => ({ default: () => <div data-testid="not-found-screen">not-found</div> }));

function renderAt(path: string) {
  window.history.replaceState(null, "", path);
  render(<ScreenSwitch />);
}

describe("normalizePathname", () => {
  it("normalizes empty or trailing slash paths", () => {
    expect(normalizePathname("")).toBe("/");
    expect(normalizePathname("/")).toBe("/");
    expect(normalizePathname("/workspaces/")).toBe("/workspaces");
    expect(normalizePathname("/workspaces/abc/")).toBe("/workspaces/abc");
  });
});

describe("ScreenSwitch", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
  });

  const cases: Array<{ path: string; testId: string }> = [
    { path: "/", testId: "home-screen" },
    { path: "/login", testId: "login-screen" },
    { path: "/auth/callback", testId: "auth-callback-screen" },
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

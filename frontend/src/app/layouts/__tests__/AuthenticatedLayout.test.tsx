import { act, render, screen } from "@testing-library/react";
import { useMemo } from "react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useConfigureAuthenticatedTopbar } from "@/app/layouts/components/topbar/AuthenticatedTopbarContext";
import { AuthenticatedLayout } from "@/app/layouts/AuthenticatedLayout";

vi.mock("@/app/layouts/components/topbar/UnifiedTopbarControls", () => ({
  UnifiedTopbarControls: () => <div data-testid="unified-topbar-controls">controls</div>,
}));

function PlainPage() {
  return <div data-testid="plain-page">plain</div>;
}

function ConfiguredPage() {
  const config = useMemo(
    () => ({
      desktopCenter: <div data-testid="desktop-slot">desktop-search</div>,
      mobileAction: <button data-testid="mobile-slot">mobile-search</button>,
    }),
    [],
  );
  useConfigureAuthenticatedTopbar(config);
  return <div data-testid="configured-page">configured</div>;
}

function renderRouter(initialEntries: string[], children: RouteObject[]) {
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <AuthenticatedLayout />,
        children,
      },
    ],
    { initialEntries },
  );

  render(<RouterProvider router={router} />);

  return router;
}

describe("AuthenticatedLayout", () => {
  it("always renders shared controls", async () => {
    renderRouter(["/"], [{ index: true, element: <PlainPage /> }]);

    expect(await screen.findByTestId("unified-topbar-controls")).toBeInTheDocument();
    expect(screen.queryByTestId("desktop-slot")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mobile-slot")).not.toBeInTheDocument();
  });

  it("renders center and mobile topbar slots when configured", async () => {
    renderRouter(["/"], [{ index: true, element: <ConfiguredPage /> }]);

    expect(await screen.findByTestId("unified-topbar-controls")).toBeInTheDocument();
    expect(screen.getByTestId("desktop-slot")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-slot")).toBeInTheDocument();
  });

  it("clears configured slots when navigating away", async () => {
    const router = renderRouter(
      ["/configured"],
      [
        { path: "configured", element: <ConfiguredPage /> },
        { path: "plain", element: <PlainPage /> },
      ],
    );

    expect(await screen.findByTestId("desktop-slot")).toBeInTheDocument();
    expect(screen.getByTestId("mobile-slot")).toBeInTheDocument();

    await act(async () => {
      await router.navigate("/plain");
    });

    expect(await screen.findByTestId("plain-page")).toBeInTheDocument();
    expect(screen.queryByTestId("desktop-slot")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mobile-slot")).not.toBeInTheDocument();
  });

  it("renders a workspace return action on organization routes", async () => {
    const user = userEvent.setup();
    const router = renderRouter(
      ["/organization/users"],
      [
        { path: "organization/*", element: <PlainPage /> },
        { path: "workspaces", element: <PlainPage /> },
      ],
    );

    expect(screen.getByRole("link", { name: "Go back to workspace" })).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole("link", { name: "Go back to workspace" }));
    });

    expect(router.state.location.pathname).toBe("/workspaces");
  });
});

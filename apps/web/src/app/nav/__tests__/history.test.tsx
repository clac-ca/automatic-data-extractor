import React from "react";
import userEvent from "@testing-library/user-event";
import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { NavProvider, useLocation, useNavigate, useNavigationBlocker } from "../history";

function LocationProbe() {
  const location = useLocation();
  return (
    <div data-testid="location">
      {location.pathname}
      {location.search}
      {location.hash}
    </div>
  );
}

function NavigateButton({ to }: { readonly to: string }) {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate(to)}>
      navigate
    </button>
  );
}

function BlockNavigation({ allow }: { readonly allow: boolean }) {
  useNavigationBlocker(() => allow, true);
  return <NavigateButton to="/blocked" />;
}

function ToggleableBlocker() {
  const [enabled, setEnabled] = React.useState(false);
  useNavigationBlocker(() => false, enabled);
  return (
    <>
      <button type="button" onClick={() => setEnabled(true)}>
        enable-blocker
      </button>
      <NavigateButton to="/workspaces/abc" />
    </>
  );
}

describe("NavProvider", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/initial?foo=1#anchor");
  });

  it("updates subscribers when the browser history emits popstate", () => {
    render(
      <NavProvider>
        <LocationProbe />
      </NavProvider>,
    );

    act(() => {
      window.history.pushState(null, "", "/workspaces/abc?view=list#summary");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(screen.getByTestId("location").textContent).toBe("/workspaces/abc?view=list#summary");
  });

  it("navigates via the useNavigate helper and reflects hash/search", async () => {
    const user = userEvent.setup();
    render(
      <NavProvider>
        <>
          <NavigateButton to="/workspaces/abc/config-builder/123?tab=editor#dirty" />
          <LocationProbe />
        </>
      </NavProvider>,
    );

    await user.click(screen.getByRole("button", { name: "navigate" }));

    expect(screen.getByTestId("location").textContent).toBe(
      "/workspaces/abc/config-builder/123?tab=editor#dirty",
    );
  });

  it("prevents navigation when a blocker denies the transition", async () => {
    const user = userEvent.setup();
    render(
      <NavProvider>
        <>
          <BlockNavigation allow={false} />
          <LocationProbe />
        </>
      </NavProvider>,
    );

    await user.click(screen.getByRole("button", { name: "navigate" }));

    expect(screen.getByTestId("location").textContent).toBe("/initial?foo=1#anchor");
  });

  it("allows navigation when blockers resolve true", async () => {
    const user = userEvent.setup();
    render(
      <NavProvider>
        <>
          <BlockNavigation allow={true} />
          <LocationProbe />
        </>
      </NavProvider>,
    );

    await user.click(screen.getByRole("button", { name: "navigate" }));

    expect(screen.getByTestId("location").textContent).toBe("/blocked");
  });

  it("restores the previous location when a popstate navigation is blocked", async () => {
    const user = userEvent.setup();
    render(
      <NavProvider>
        <>
          <ToggleableBlocker />
          <LocationProbe />
        </>
      </NavProvider>,
    );

    await user.click(screen.getByRole("button", { name: "navigate" }));
    expect(screen.getByTestId("location").textContent).toBe("/workspaces/abc");

    await user.click(screen.getByRole("button", { name: "enable-blocker" }));

    act(() => {
      window.history.pushState(null, "", "/initial?foo=1#anchor");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(screen.getByTestId("location").textContent).toBe("/workspaces/abc");
  });
});

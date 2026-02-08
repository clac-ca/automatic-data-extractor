import React from "react";
import userEvent from "@testing-library/user-event";
import { render as rtlRender, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { createMemoryRouter, RouterProvider, useLocation, useNavigate } from "react-router-dom";
import { AllProviders } from "@/test/test-utils";

import { useUnsavedChangesGuard, UNSAVED_CHANGES_PROMPT } from "../useUnsavedChangesGuard";

function GuardHarness({ confirm }: { readonly confirm: (message: string) => boolean }) {
  const [dirty, setDirty] = React.useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useUnsavedChangesGuard({ isDirty: dirty, confirm });

  return (
    <div>
      <button type="button" onClick={() => setDirty(true)}>
        mark-dirty
      </button>
      <button type="button" onClick={() => navigate("/other")}>
        navigate-away
      </button>
      <button type="button" onClick={() => navigate(`${location.pathname}?file=foo`, { replace: true })}>
        update-query
      </button>
    </div>
  );
}

describe("useUnsavedChangesGuard", () => {
  function renderWithRouter(ui: React.ReactElement, route: string) {
    const router = createMemoryRouter(
      [
        {
          path: "*",
          element: <AllProviders>{ui}</AllProviders>,
        },
      ],
      { initialEntries: [route] },
    );
    return { router, ...rtlRender(<RouterProvider router={router} />) };
  }

  it("blocks navigation when the user cancels and wires beforeunload", async () => {
    const confirmMock = vi.fn().mockReturnValue(false);
    const { router } = renderWithRouter(
      <GuardHarness confirm={confirmMock} />,
      "/workspaces/acme/configurations/foo",
    );

    await userEvent.click(screen.getByRole("button", { name: "mark-dirty" }));
    await userEvent.click(screen.getByRole("button", { name: "navigate-away" }));

    expect(confirmMock).toHaveBeenCalledWith(UNSAVED_CHANGES_PROMPT);
    expect(router.state.location.pathname).toBe("/workspaces/acme/configurations/foo");

    const event = new Event("beforeunload", { cancelable: true });
    Object.defineProperty(event, "returnValue", { writable: true, value: undefined });
    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(event.returnValue).toBe(UNSAVED_CHANGES_PROMPT);
  });

  it("allows navigation when confirmed and ignores internal query updates", async () => {
    const confirmMock = vi.fn().mockReturnValue(true);
    const { router } = renderWithRouter(
      <GuardHarness confirm={confirmMock} />,
      "/workspaces/acme/configurations/foo",
    );

    await userEvent.click(screen.getByRole("button", { name: "mark-dirty" }));
    await userEvent.click(screen.getByRole("button", { name: "update-query" }));

    expect(confirmMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "navigate-away" }));

    expect(confirmMock).toHaveBeenCalledWith(UNSAVED_CHANGES_PROMPT);
    await waitFor(() => expect(router.state.location.pathname).toBe("/other"));
  });
});

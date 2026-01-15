import React from "react";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/test-utils";
import { describe, expect, it, vi } from "vitest";

import { useNavigate } from "react-router-dom";

import { useUnsavedChangesGuard, UNSAVED_CHANGES_PROMPT } from "../useUnsavedChangesGuard";

function GuardHarness({ confirm }: { readonly confirm: (message: string) => boolean }) {
  const [dirty, setDirty] = React.useState(false);
  const navigate = useNavigate();

  useUnsavedChangesGuard({ isDirty: dirty, confirm });

  return (
    <div>
      <button type="button" onClick={() => setDirty(true)}>
        mark-dirty
      </button>
      <button type="button" onClick={() => navigate("/other")}>
        navigate-away
      </button>
      <button type="button" onClick={() => navigate(`${window.location.pathname}?file=foo`, { replace: true })}>
        update-query
      </button>
    </div>
  );
}

describe("useUnsavedChangesGuard", () => {
  it("blocks navigation when the user cancels and wires beforeunload", async () => {
    window.history.replaceState(null, "", "/workspaces/acme/config-builder/foo/editor");

    const confirmMock = vi.fn().mockReturnValue(false);
    render(<GuardHarness confirm={confirmMock} />);

    await userEvent.click(screen.getByRole("button", { name: "mark-dirty" }));
    await userEvent.click(screen.getByRole("button", { name: "navigate-away" }));

    expect(confirmMock).toHaveBeenCalledWith(UNSAVED_CHANGES_PROMPT);
    expect(window.location.pathname).toBe("/workspaces/acme/config-builder/foo/editor");

    const event = new Event("beforeunload", { cancelable: true });
    Object.defineProperty(event, "returnValue", { writable: true, value: undefined });
    window.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
    expect(event.returnValue).toBe(UNSAVED_CHANGES_PROMPT);
  });

  it("allows navigation when confirmed and ignores internal query updates", async () => {
    window.history.replaceState(null, "", "/workspaces/acme/config-builder/foo/editor");

    const confirmMock = vi.fn().mockReturnValue(true);
    render(<GuardHarness confirm={confirmMock} />);

    await userEvent.click(screen.getByRole("button", { name: "mark-dirty" }));
    await userEvent.click(screen.getByRole("button", { name: "update-query" }));

    expect(confirmMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "navigate-away" }));

    expect(confirmMock).toHaveBeenCalledWith(UNSAVED_CHANGES_PROMPT);
    expect(window.location.pathname).toBe("/other");
  });
});

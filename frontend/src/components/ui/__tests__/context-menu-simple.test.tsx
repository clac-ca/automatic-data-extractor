import { fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

import { ContextMenu } from "../context-menu-simple";

describe("ContextMenu", () => {
  it("ignores secondary pointer-down outside to avoid immediate close on right-click flows", async () => {
    const onClose = vi.fn();
    render(
      <ContextMenu
        open
        position={{ x: 120, y: 80 }}
        onClose={onClose}
        items={[
          {
            id: "open",
            label: "Open",
            onSelect: vi.fn(),
          },
        ]}
      />,
    );

    await screen.findByRole("menu");
    fireEvent.pointerDown(document.body, { button: 2, pointerType: "mouse" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on primary pointer-down outside", async () => {
    const onClose = vi.fn();
    render(
      <ContextMenu
        open
        position={{ x: 120, y: 80 }}
        onClose={onClose}
        items={[
          {
            id: "open",
            label: "Open",
            onSelect: vi.fn(),
          },
        ]}
      />,
    );

    await screen.findByRole("menu");
    fireEvent.pointerDown(document.body, { button: 0, pointerType: "mouse" });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});

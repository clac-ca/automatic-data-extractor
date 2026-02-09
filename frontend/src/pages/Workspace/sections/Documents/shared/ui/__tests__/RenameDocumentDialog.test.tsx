import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";

import { RenameDocumentDialog } from "../RenameDocumentDialog";

describe("RenameDocumentDialog", () => {
  it("renders base name with a locked extension suffix", () => {
    render(
      <RenameDocumentDialog
        open
        documentName="Quarterly Intake.xlsx"
        onOpenChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Name")).toHaveValue("Quarterly Intake");
    expect(screen.getByText(".xlsx")).toBeInTheDocument();
  });

  it("submits on Enter with extension preserved", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(
      <RenameDocumentDialog
        open
        documentName="source.csv"
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const input = screen.getByLabelText("Name");
    await user.clear(input);
    await user.type(input, "renamed");
    await user.keyboard("{Enter}");

    expect(onSubmit).toHaveBeenCalledWith("renamed.csv");
  });

  it("cancels on Escape", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();

    render(
      <RenameDocumentDialog
        open
        documentName="source.xlsx"
        onOpenChange={onOpenChange}
        onSubmit={vi.fn()}
      />,
    );

    const input = screen.getByLabelText("Name");
    input.focus();
    await user.keyboard("{Escape}");

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

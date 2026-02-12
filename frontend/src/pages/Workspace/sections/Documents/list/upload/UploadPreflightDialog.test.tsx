import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen, waitFor } from "@/test/test-utils";

import { UploadPreflightDialog } from "./UploadPreflightDialog";

describe("UploadPreflightDialog", () => {
  it("defaults to active-sheet processing", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(
      <UploadPreflightDialog
        open
        files={[new File(["csv"], "input.csv", { type: "text/csv" })]}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        processingPaused={false}
        configMissing={false}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith([
        {
          file: expect.any(File),
          runOptions: {
            active_sheet_only: true,
          },
        },
      ]);
    });
  });

  it("applies all-sheet processing to every queued file", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(
      <UploadPreflightDialog
        open
        files={[
          new File(["a"], "one.csv", { type: "text/csv" }),
          new File(["b"], "two.csv", { type: "text/csv" }),
        ]}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        processingPaused={false}
        configMissing={false}
      />,
    );

    await user.click(screen.getByLabelText("All sheets"));
    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith([
        {
          file: expect.any(File),
          runOptions: { active_sheet_only: false },
        },
        {
          file: expect.any(File),
          runOptions: { active_sheet_only: false },
        },
      ]);
    });
  });

  it("warns when workbook uploads cannot use specific-sheet selection", async () => {
    render(
      <UploadPreflightDialog
        open
        files={[
          new File(
            ["xlsx"],
            "book.xlsx",
            { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
          ),
        ]}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        processingPaused={false}
        configMissing={false}
      />,
    );

    expect(screen.getByText(/Worksheet-level selection is unavailable for direct uploads/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Specific sheets")).not.toBeInTheDocument();
  });
});

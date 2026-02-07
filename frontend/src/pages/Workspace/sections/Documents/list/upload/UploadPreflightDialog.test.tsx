import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen, waitFor } from "@/test/test-utils";

import { UploadPreflightDialog } from "./UploadPreflightDialog";
import { readWorkbookSheetNames } from "./sheetSelection";

vi.mock("./sheetSelection", async () => {
  const actual = await vi.importActual<typeof import("./sheetSelection")>("./sheetSelection");
  return {
    ...actual,
    readWorkbookSheetNames: vi.fn(),
  };
});

const mockedReadWorkbookSheetNames = vi.mocked(readWorkbookSheetNames);

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

  it("supports selecting specific sheets for a single workbook upload", async () => {
    mockedReadWorkbookSheetNames.mockResolvedValueOnce(["Sheet A", "Sheet B"]);
    const user = userEvent.setup();
    const onConfirm = vi.fn();

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
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        processingPaused={false}
        configMissing={false}
      />,
    );

    await screen.findByText("Worksheets (2)");
    await user.click(screen.getByLabelText("Specific sheets"));
    await user.click(screen.getByRole("checkbox", { name: "Sheet A" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith([
        {
          file: expect.any(File),
          runOptions: {
            active_sheet_only: false,
            input_sheet_names: ["Sheet A"],
          },
        },
      ]);
    });
  });
});

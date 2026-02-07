import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen, waitFor } from "@/test/test-utils";
import { fetchDocumentSheets } from "@/api/documents";

import { ReprocessPreflightDialog } from "./ReprocessPreflightDialog";

vi.mock("@/api/documents", async () => {
  const actual = await vi.importActual<typeof import("@/api/documents")>("@/api/documents");
  return {
    ...actual,
    fetchDocumentSheets: vi.fn(),
  };
});

const mockedFetchDocumentSheets = vi.mocked(fetchDocumentSheets);

describe("ReprocessPreflightDialog", () => {
  it("defaults to active-sheet processing", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(
      <ReprocessPreflightDialog
        open
        workspaceId="workspace-1"
        documents={[
          { id: "doc-1", name: "input.csv", fileType: "csv" },
        ]}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        processingPaused={false}
        configMissing={false}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reprocess" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith({
        active_sheet_only: true,
      });
    });
  });

  it("applies all-sheet processing to a multi-document selection", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(
      <ReprocessPreflightDialog
        open
        workspaceId="workspace-1"
        documents={[
          { id: "doc-1", name: "one.csv", fileType: "csv" },
          { id: "doc-2", name: "two.csv", fileType: "csv" },
        ]}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        processingPaused={false}
        configMissing={false}
      />,
    );

    await user.click(screen.getByLabelText("All sheets"));
    await user.click(screen.getByRole("button", { name: "Reprocess" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith({
        active_sheet_only: false,
      });
    });
  });

  it("supports specific sheet selection for a single workbook", async () => {
    mockedFetchDocumentSheets.mockResolvedValueOnce([
      { name: "Sheet A", index: 0, kind: "worksheet", is_active: true },
      { name: "Sheet B", index: 1, kind: "worksheet", is_active: false },
    ]);
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(
      <ReprocessPreflightDialog
        open
        workspaceId="workspace-1"
        documents={[
          { id: "doc-1", name: "book.xlsx", fileType: "xlsx" },
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
    await user.click(screen.getByRole("button", { name: "Reprocess" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith({
        active_sheet_only: false,
        input_sheet_names: ["Sheet A"],
      });
    });
  });
});

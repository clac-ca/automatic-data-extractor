import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { ActionsCell } from "../ActionsCell";

function makeDocument(): DocumentRow {
  return {
    id: "doc_1",
    workspaceId: "ws_1",
    name: "source.csv",
    fileType: "csv",
    byteSize: 16,
    commentCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-01T00:00:00Z",
    tags: [],
    lastRun: {
      id: "run_1",
      status: "failed",
      createdAt: "2026-01-01T00:00:00Z",
      startedAt: "2026-01-01T00:01:00Z",
      completedAt: "2026-01-01T00:02:00Z",
      errorMessage: "engine failed",
    },
  } as DocumentRow;
}

describe("ActionsCell", () => {
  it("always exposes unified download and keeps original in menu", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onDownloadLatest = vi.fn();
    const onDownloadOriginal = vi.fn();

    render(
      <ActionsCell
        document={document}
        lifecycle="active"
        onOpenDocument={vi.fn()}
        onOpenActivity={vi.fn()}
        isBusy={false}
        onRenameRequest={vi.fn()}
        onDeleteRequest={vi.fn()}
        onRestoreRequest={vi.fn()}
        onDownloadLatest={onDownloadLatest}
        onDownloadOriginal={onDownloadOriginal}
        onReprocessRequest={vi.fn()}
        onCancelRunRequest={vi.fn()}
      />,
    );

    await user.click(screen.getByLabelText("Download latest document"));
    expect(onDownloadLatest).toHaveBeenCalledWith(document);
    expect(screen.queryByText(/Download normalized/i)).not.toBeInTheDocument();

    await user.click(screen.getByLabelText("More actions"));
    await user.click(screen.getByText("Download original"));
    expect(onDownloadOriginal).toHaveBeenCalledWith(document);
  });
});

import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentTicketHeader } from "../DocumentTicketHeader";

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
      status: "succeeded",
      createdAt: "2026-01-01T00:00:00Z",
      startedAt: "2026-01-01T00:01:00Z",
      completedAt: "2026-01-01T00:02:00Z",
      errorMessage: null,
    },
  } as DocumentRow;
}

describe("DocumentTicketHeader", () => {
  it("uses unified download as primary and exposes original in the menu", async () => {
    const user = userEvent.setup();
    const document = makeDocument();

    render(
      <DocumentTicketHeader
        workspaceId="ws_1"
        document={document}
        onBack={vi.fn()}
        onRenameRequest={vi.fn()}
        onReprocessRequest={vi.fn()}
        onCancelRunRequest={vi.fn()}
      />,
    );

    const unified = screen.getByRole("link", { name: "Download" });
    expect(unified).toHaveAttribute(
      "href",
      "/api/v1/workspaces/ws_1/documents/doc_1/download",
    );
    expect(screen.queryByText("Download normalized")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "More" }));

    const original = screen.getByRole("menuitem", { name: "Download original" });
    expect(original).toHaveAttribute(
      "href",
      "/api/v1/workspaces/ws_1/documents/doc_1/original/download",
    );
  });
});

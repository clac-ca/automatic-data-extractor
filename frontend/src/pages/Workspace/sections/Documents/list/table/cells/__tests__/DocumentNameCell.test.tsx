import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render, screen } from "@/test/test-utils";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import { DocumentNameCell } from "../DocumentNameCell";

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
    assignee: {
      id: "user_other",
      name: "Other",
      email: "other@example.com",
    },
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

describe("DocumentNameCell", () => {
  it("triggers rename from the row action button", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onRenameRequest = vi.fn();

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        onRenameRequest={onRenameRequest}
      />,
    );

    await user.click(screen.getByLabelText("Rename document"));

    expect(onRenameRequest).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("renders shared overflow actions and supports assign-to-me", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onAssignToMe = vi.fn();
    const onRenameRequest = vi.fn();
    const onDownloadLatest = vi.fn();
    const onDownloadOriginal = vi.fn();
    const onDownloadEventsLog = vi.fn();

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        currentUserId="user_me"
        onAssignToMe={onAssignToMe}
        onRenameRequest={onRenameRequest}
        onDownloadLatest={onDownloadLatest}
        onDownloadOriginal={onDownloadOriginal}
        onDownloadEventsLog={onDownloadEventsLog}
      />,
    );

    await user.click(screen.getByLabelText("More actions"));
    expect(screen.getByRole("menuitem", { name: "Download" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Download original" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Download events log" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Assign to me" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Assign to me" }));

    expect(onAssignToMe).toHaveBeenCalledTimes(1);
  });

  it("triggers the overflow rename handler", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onRenameRequest = vi.fn();

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        onRenameRequest={onRenameRequest}
      />,
    );

    await user.click(screen.getByLabelText("More actions"));
    await user.click(screen.getByRole("menuitem", { name: "Rename" }));

    expect(onRenameRequest).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("triggers the overflow events log handler", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onDownloadEventsLog = vi.fn();

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        onDownloadEventsLog={onDownloadEventsLog}
      />,
    );

    await user.click(screen.getByLabelText("More actions"));
    await user.click(screen.getByRole("menuitem", { name: "Download events log" }));

    expect(onDownloadEventsLog).toHaveBeenCalledWith(document);
  });
});

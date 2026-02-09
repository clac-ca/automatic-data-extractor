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
  it("supports inline rename via F2 + Enter", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onRename = vi.fn().mockResolvedValue(undefined);

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        onRename={onRename}
      />,
    );

    const name = screen.getByText("source.csv");
    name.focus();
    await user.keyboard("{F2}");

    const input = await screen.findByRole("textbox");
    await user.clear(input);
    await user.type(input, "renamed");
    await user.keyboard("{Enter}");

    expect(onRename).toHaveBeenCalledWith("renamed.csv");
  });

  it("renders shared overflow actions and supports assign-to-me", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onAssignToMe = vi.fn();
    const onRename = vi.fn().mockResolvedValue(undefined);
    const onDownloadLatest = vi.fn();
    const onDownloadOriginal = vi.fn();

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        currentUserId="user_me"
        onAssignToMe={onAssignToMe}
        onRename={onRename}
        onDownloadLatest={onDownloadLatest}
        onDownloadOriginal={onDownloadOriginal}
      />,
    );

    await user.click(screen.getByLabelText("More actions"));
    expect(screen.getByRole("menuitem", { name: "Download" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Download original" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Assign to me" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Assign to me" }));

    expect(onAssignToMe).toHaveBeenCalledTimes(1);
  });

  it("locks extension while renaming inline", async () => {
    const user = userEvent.setup();
    const document = makeDocument();
    const onRename = vi.fn().mockResolvedValue(undefined);

    render(
      <DocumentNameCell
        document={document}
        lifecycle="active"
        presenceEntries={[]}
        onRename={onRename}
      />,
    );

    const name = screen.getByText("source.csv");
    name.focus();
    await user.keyboard("{F2}");

    expect(screen.getByText(".csv")).toBeInTheDocument();

    const input = await screen.findByRole("textbox");
    await user.clear(input);
    await user.type(input, "new-name");
    await user.keyboard("{Enter}");

    expect(onRename).toHaveBeenCalledWith("new-name.csv");
    expect(onRename).not.toHaveBeenCalledWith("new-name");
  });
});

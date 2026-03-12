import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentActivityFeed } from "./DocumentActivityFeed";

const currentUser = {
  id: "user-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
};

function makeItems() {
  return [
    {
      key: "note:thread-note",
      replyTargetKey: "note:thread-note",
      id: "thread-note",
      type: "note" as const,
      activityAt: "2026-01-03T00:00:00Z",
      thread: {
        id: "thread-note",
        workspaceId: "ws-1",
        documentId: "doc-1",
        anchorType: "note" as const,
        anchorId: null,
        activityAt: "2026-01-03T00:00:00Z",
        commentCount: 1,
        comments: [
          {
            id: "comment-1",
            workspaceId: "ws-1",
            documentId: "doc-1",
            threadId: "thread-note",
            body: "Delete this note",
            author: currentUser,
            mentions: [],
            createdAt: "2026-01-03T00:00:00Z",
            updatedAt: "2026-01-03T00:00:00Z",
            editedAt: null,
          },
        ],
      },
    },
  ];
}

function buildProps({
  deletingCommentId = null,
  deleteErrorCommentId = null,
  deleteErrorMessage = null,
  onDeleteComment = vi.fn().mockResolvedValue(undefined) as (commentId: string) => Promise<unknown>,
}: {
  deletingCommentId?: string | null;
  deleteErrorCommentId?: string | null;
  deleteErrorMessage?: string | null;
  onDeleteComment?: (commentId: string) => Promise<unknown>;
}) {
  return {
    workspaceId: "ws-1",
    currentUser,
    items: makeItems(),
    isLoading: false,
    hasError: false,
    showDiscussions: true,
    activeReplyTargetKey: null,
    replyDraftsByTargetKey: {},
    submittingReplyTargetKey: null,
    replyErrorTargetKey: null,
    activeEditCommentId: null,
    editDraftsByCommentId: {},
    submittingEditCommentId: null,
    editErrorCommentId: null,
    editErrorMessage: null,
    deletingCommentId,
    deleteErrorCommentId,
    deleteErrorMessage,
    onStartReply: vi.fn(),
    onCancelReply: vi.fn(),
    onReplyDraftChange: vi.fn(),
    onSubmitReply: vi.fn(),
    onStartEdit: vi.fn(),
    onCancelEdit: vi.fn(),
    onEditDraftChange: vi.fn(),
    onSubmitEdit: vi.fn(),
    onDeleteComment,
  };
}

function renderFeed(overrides: Parameters<typeof buildProps>[0] = {}) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  const props = buildProps(overrides);

  return {
    client,
    props,
    ...render(
      <QueryClientProvider client={client}>
        <DocumentActivityFeed {...props} />
      </QueryClientProvider>,
    ),
  };
}

describe("DocumentActivityFeed", () => {
  it("opens a confirmation dialog before deleting a comment", async () => {
    const user = userEvent.setup();
    const onDeleteComment = vi.fn().mockResolvedValue(undefined);

    renderFeed({
      onDeleteComment: onDeleteComment as unknown as (commentId: string) => Promise<unknown>,
    });

    await user.click(screen.getByRole("button", { name: "Delete" }));

    const dialog = screen.getByRole("dialog", { name: "Delete comment?" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("Delete this note")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete comment" }));

    expect(onDeleteComment).toHaveBeenCalledWith("comment-1");
  });

  it("disables the confirmation controls while the delete mutation is pending", async () => {
    const user = userEvent.setup();
    const onDeleteComment = vi.fn();
    const deleteHandler = onDeleteComment as unknown as (commentId: string) => Promise<unknown>;
    const rendered = renderFeed({ onDeleteComment: deleteHandler });

    await user.click(screen.getByRole("button", { name: "Delete" }));

    rendered.rerender(
      <QueryClientProvider client={rendered.client}>
        <DocumentActivityFeed
          {...buildProps({
            onDeleteComment: deleteHandler,
            deletingCommentId: "comment-1",
          })}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("button", { name: "Delete comment" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentCommentThreadCard } from "./DocumentCommentThreadCard";

const currentUser = {
  id: "user-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
};

const thread = {
  id: "thread-note",
  workspaceId: "ws-1",
  documentId: "doc-1",
  anchorType: "note" as const,
  anchorId: null,
  activityAt: "2026-01-03T00:00:00Z",
  commentCount: 2,
  comments: [
    {
      id: "comment-1",
      workspaceId: "ws-1",
      documentId: "doc-1",
      threadId: "thread-note",
      body: "First note",
      author: currentUser,
      mentions: [],
      createdAt: "2026-01-03T00:00:00Z",
      updatedAt: "2026-01-03T00:00:00Z",
      editedAt: null,
    },
    {
      id: "comment-2",
      workspaceId: "ws-1",
      documentId: "doc-1",
      threadId: "thread-note",
      body: "Follow-up",
      author: {
        id: "user-2",
        name: "Reviewer",
        email: "reviewer@example.com",
      },
      mentions: [],
      createdAt: "2026-01-03T00:05:00Z",
      updatedAt: "2026-01-03T00:05:00Z",
      editedAt: null,
    },
  ],
};

function renderWithQuery(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("DocumentCommentThreadCard", () => {
  it("renders note threads without a generic discussion heading", () => {
    renderWithQuery(
      <DocumentCommentThreadCard
        variant="note"
        workspaceId="ws-1"
        currentUser={currentUser}
        thread={thread}
        isReplyOpen={false}
        activeEditCommentId={null}
        submittingEditCommentId={null}
        editErrorCommentId={null}
        editErrorMessage={null}
        onStartReply={vi.fn()}
        onCancelReply={vi.fn()}
        onSubmitReply={vi.fn()}
        onStartEdit={vi.fn()}
        onCancelEdit={vi.fn()}
        onSubmitEdit={vi.fn()}
      />,
    );

    expect(screen.queryByText("Discussion")).not.toBeInTheDocument();
    expect(screen.getByText("First note")).toBeInTheDocument();
    expect(screen.getByText("Follow-up")).toBeInTheDocument();
  });

  it("keeps non-edited replies visible while one comment is in edit mode", () => {
    renderWithQuery(
      <DocumentCommentThreadCard
        variant="note"
        workspaceId="ws-1"
        currentUser={currentUser}
        thread={thread}
        isReplyOpen={false}
        activeEditCommentId="comment-1"
        submittingEditCommentId={null}
        editErrorCommentId={null}
        editErrorMessage={null}
        onStartReply={vi.fn()}
        onCancelReply={vi.fn()}
        onSubmitReply={vi.fn()}
        onStartEdit={vi.fn()}
        onCancelEdit={vi.fn()}
        onSubmitEdit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Update your comment...")).toBeInTheDocument();
    expect(screen.getByText("Follow-up")).toBeInTheDocument();
  });

  it("does not show Edited for a fresh comment with a non-meaningful edited timestamp", () => {
    renderWithQuery(
      <DocumentCommentThreadCard
        variant="note"
        workspaceId="ws-1"
        currentUser={currentUser}
        thread={{
          ...thread,
          comments: [
            {
              ...thread.comments[0],
              createdAt: "2026-01-03T00:00:00.000Z",
              editedAt: "2026-01-03T00:00:00.000Z",
            },
          ],
        }}
        isReplyOpen={false}
        activeEditCommentId={null}
        submittingEditCommentId={null}
        editErrorCommentId={null}
        editErrorMessage={null}
        onStartReply={vi.fn()}
        onCancelReply={vi.fn()}
        onSubmitReply={vi.fn()}
        onStartEdit={vi.fn()}
        onCancelEdit={vi.fn()}
        onSubmitEdit={vi.fn()}
      />,
    );

    expect(screen.queryByText("Edited")).not.toBeInTheDocument();
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Timeline } from "@/components/ui/timeline";

import { DocumentActivityFeedItem } from "./DocumentActivityFeedItem";

const currentUser = {
  id: "user-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
};

function renderWithQuery(ui: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <Timeline>{ui}</Timeline>
    </QueryClientProvider>,
  );
}

describe("DocumentActivityFeedItem", () => {
  it("keeps the events filter free of thread content and reply actions", () => {
    renderWithQuery(
      <DocumentActivityFeedItem
        item={{
          key: "document:doc-1",
          replyTargetKey: "document:doc-1",
          id: "doc-1",
          type: "document",
          activityAt: "2026-01-01T00:00:00Z",
          title: "Document uploaded",
          uploader: currentUser,
          thread: {
            id: "thread-document",
            workspaceId: "ws-1",
            documentId: "doc-1",
            anchorType: "document",
            anchorId: "doc-1",
            activityAt: "2026-01-01T00:00:00Z",
            commentCount: 1,
            comments: [
              {
                id: "comment-1",
                workspaceId: "ws-1",
                documentId: "doc-1",
                threadId: "thread-document",
                body: "Hidden discussion",
                author: currentUser,
                mentions: [],
                createdAt: "2026-01-01T00:00:00Z",
                updatedAt: "2026-01-01T00:00:00Z",
                editedAt: null,
              },
            ],
          },
        }}
        workspaceId="ws-1"
        currentUser={currentUser}
        showDiscussions={false}
        activeReplyTargetKey={null}
        replyDraft={null}
        submittingReplyTargetKey={null}
        replyErrorTargetKey={null}
        activeEditCommentId={null}
        activeEditDraft={null}
        submittingEditCommentId={null}
        editErrorCommentId={null}
        editErrorMessage={null}
        onStartReply={vi.fn()}
        onCancelReply={vi.fn()}
        onReplyDraftChange={vi.fn()}
        onSubmitReply={vi.fn()}
        onStartEdit={vi.fn()}
        onCancelEdit={vi.fn()}
        onEditDraftChange={vi.fn()}
        onSubmitEdit={vi.fn()}
      />,
    );

    expect(screen.getByText("Document uploaded")).toBeInTheDocument();
    expect(screen.queryByText("Hidden discussion")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reply" })).not.toBeInTheDocument();
  });
});

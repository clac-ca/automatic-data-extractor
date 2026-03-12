import { describe, expect, it } from "vitest";

import type { ActivityResponseData, ActivityThread } from "../model";
import {
  appendCommentToThread,
  appendOptimisticNote,
  attachThreadToActivityItem,
} from "./activityTimelineCache";

function makeActivityData(): ActivityResponseData {
  return {
    items: [
      {
        key: "document:doc-1",
        replyTargetKey: "document:doc-1",
        id: "doc-1",
        type: "document",
        activityAt: "2026-01-01T00:00:00Z",
        title: "Document uploaded",
        uploader: null,
        thread: null,
      },
      {
        key: "run:run-1",
        replyTargetKey: "run:run-1",
        id: "run-1",
        type: "run",
        activityAt: "2026-01-02T00:00:00Z",
        run: {
          id: "run-1",
          operation: "process",
          status: "succeeded",
          createdAt: "2026-01-02T00:00:00Z",
          startedAt: "2026-01-02T00:00:01Z",
          completedAt: "2026-01-02T00:00:05Z",
          durationSeconds: 4,
          exitCode: 0,
          errorMessage: null,
        },
        thread: null,
      },
    ],
  };
}

function makeThread(): ActivityThread {
  return {
    id: "thread-run",
    workspaceId: "ws-1",
    documentId: "doc-1",
    anchorType: "run",
    anchorId: "run-1",
    activityAt: "2026-01-02T00:00:00Z",
    commentCount: 1,
    comments: [
      {
        id: "comment-1",
        workspaceId: "ws-1",
        documentId: "doc-1",
        threadId: "thread-run",
        body: "Root comment",
        author: {
          id: "user-1",
          name: "Owner",
          email: "owner@example.com",
        },
        mentions: [],
        createdAt: "2026-01-02T00:10:00Z",
        updatedAt: "2026-01-02T00:10:00Z",
        editedAt: null,
      },
    ],
  };
}

describe("activityTimelineCache", () => {
  it("attaches a thread without moving the parent activity item", () => {
    const updated = attachThreadToActivityItem(
      makeActivityData(),
      "run",
      "run-1",
      makeThread(),
    );

    expect(updated.items.map((item) => item.key)).toEqual([
      "document:doc-1",
      "run:run-1",
    ]);
    expect(updated.items[1].thread?.id).toBe("thread-run");
  });

  it("appends replies inside the existing thread in place", () => {
    const initial = attachThreadToActivityItem(
      makeActivityData(),
      "run",
      "run-1",
      makeThread(),
    );

    const updated = appendCommentToThread(initial, "thread-run", {
      id: "comment-2",
      workspaceId: "ws-1",
      documentId: "doc-1",
      threadId: "thread-run",
      body: "Follow up",
      author: {
        id: "user-2",
        name: "Reviewer",
        email: "reviewer@example.com",
      },
      mentions: [],
      createdAt: "2026-01-02T00:20:00Z",
      updatedAt: "2026-01-02T00:20:00Z",
      editedAt: null,
    });

    expect(updated.items[1].thread?.comments.map((comment) => comment.id)).toEqual([
      "comment-1",
      "comment-2",
    ]);
    expect(updated.items.map((item) => item.key)).toEqual([
      "document:doc-1",
      "run:run-1",
    ]);
  });

  it("appends optimistic notes to the bottom of the timeline", () => {
    const updated = appendOptimisticNote(makeActivityData(), {
      key: "note:thread-note",
      replyTargetKey: "note:thread-note",
      id: "thread-note",
      type: "note",
      activityAt: "2026-01-03T00:00:00Z",
      thread: {
        id: "thread-note",
        workspaceId: "ws-1",
        documentId: "doc-1",
        anchorType: "note",
        anchorId: null,
        activityAt: "2026-01-03T00:00:00Z",
        commentCount: 1,
        comments: [],
      },
    });

    expect(updated.items.at(-1)?.key).toBe("note:thread-note");
  });
});

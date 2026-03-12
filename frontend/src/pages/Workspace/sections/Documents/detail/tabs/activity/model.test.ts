import { describe, expect, it } from "vitest";

import type { DocumentActivityResponse } from "@/api/documents";

import {
  buildActivityItems,
  filterActivityItems,
  normalizeActivityResponse,
} from "./model";

function makeActivity(): DocumentActivityResponse {
  return {
    items: [
      {
        id: "document:doc-1",
        type: "document",
        activityAt: "2026-01-01T00:00:00Z",
        title: "Document uploaded",
        uploader: {
          id: "user-1",
          name: "Uploader",
          email: "uploader@example.com",
        },
        thread: null,
      },
      {
        id: "run:run-1",
        type: "run",
        activityAt: "2026-01-02T00:00:00Z",
        run: {
          id: "run-1",
          operation: "process",
          status: "succeeded",
          createdAt: "2026-01-02T00:00:00Z",
          startedAt: "2026-01-02T00:00:05Z",
          completedAt: "2026-01-02T00:00:12Z",
          durationSeconds: 7,
          exitCode: 0,
          errorMessage: null,
        },
        thread: {
          id: "thread-run",
          workspaceId: "ws-1",
          documentId: "doc-1",
          anchorType: "run",
          anchorId: "run-1",
          activityAt: "2026-01-02T00:00:00Z",
          commentCount: 1,
          comments: [
            {
              id: "comment-2",
              workspaceId: "ws-1",
              documentId: "doc-1",
              threadId: "thread-run",
              body: "Run discussion",
              author: {
                id: "user-2",
                name: "Reviewer",
                email: "reviewer@example.com",
              },
              mentions: [],
              createdAt: "2026-01-02T01:00:00Z",
              updatedAt: "2026-01-02T01:00:00Z",
              editedAt: null,
            },
          ],
        },
      },
      {
        id: "note:thread-note",
        type: "note",
        activityAt: "2026-01-03T00:00:00Z",
        thread: {
          id: "thread-note",
          workspaceId: "ws-1",
          documentId: "doc-1",
          anchorType: "note",
          anchorId: null,
          activityAt: "2026-01-03T00:00:00Z",
          commentCount: 2,
          comments: [
            {
              id: "comment-3",
              workspaceId: "ws-1",
              documentId: "doc-1",
              threadId: "thread-note",
              body: "First note",
              author: {
                id: "user-3",
                name: "Owner",
                email: "owner@example.com",
              },
              mentions: [],
              createdAt: "2026-01-03T00:00:00Z",
              updatedAt: "2026-01-03T00:00:00Z",
              editedAt: null,
            },
            {
              id: "comment-4",
              workspaceId: "ws-1",
              documentId: "doc-1",
              threadId: "thread-note",
              body: "Follow-up",
              author: {
                id: "user-4",
                name: "Teammate",
                email: "teammate@example.com",
              },
              mentions: [],
              createdAt: "2026-01-03T02:00:00Z",
              updatedAt: "2026-01-03T02:00:00Z",
              editedAt: null,
            },
          ],
        },
      },
    ],
  };
}

describe("activity model", () => {
  it("normalizes activity into oldest-first timeline items", () => {
    const normalized = normalizeActivityResponse(makeActivity());
    const items = buildActivityItems(normalized);

    expect(items).toHaveLength(3);
    expect(items[0].type).toBe("document");
    expect(items[0].id).toBe("doc-1");
    expect(items[0].key).toBe("document:doc-1");
    expect(items[1].type).toBe("run");
    expect(items[1].id).toBe("run-1");
    expect(items[1].key).toBe("run:run-1");
    expect(items[2].type).toBe("note");
    expect(items[2].id).toBe("thread-note");
    expect(items[2].key).toBe("note:thread-note");
  });

  it("keeps discussion filters in timeline order", () => {
    const items = buildActivityItems(normalizeActivityResponse(makeActivity()));

    expect(filterActivityItems(items, "comments").map((item) => item.type)).toEqual(["run", "note"]);
    expect(filterActivityItems(items, "events").map((item) => item.type)).toEqual(["document", "run"]);
    expect(filterActivityItems(items, "all")).toHaveLength(3);
  });
});

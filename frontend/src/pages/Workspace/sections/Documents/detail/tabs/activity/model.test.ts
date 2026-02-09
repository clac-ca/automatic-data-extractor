import { describe, expect, it } from "vitest";

import type { RunResource } from "@/api/runs/api";
import type { DocumentRow } from "@/pages/Workspace/sections/Documents/shared/types";

import type { DocumentCommentItem } from "../comments/hooks/useDocumentComments";
import {
  buildActivityItems,
  filterActivityItems,
  getActivityCounts,
} from "./model";

function makeDocument(): DocumentRow {
  return {
    id: "doc_1",
    workspaceId: "ws_1",
    name: "sample.xlsx",
    fileType: "xlsx",
    byteSize: 100,
    commentCount: 1,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    activityAt: "2026-01-03T00:00:00Z",
    tags: [],
    uploader: { id: "user_1", name: "Uploader", email: "uploader@example.com" },
    lastRun: null,
  } as DocumentRow;
}

function makeRun(): RunResource {
  return {
    id: "run_1",
    object: "ade.run",
    workspace_id: "ws_1",
    configuration_id: "config_1",
    operation: "process",
    status: "succeeded",
    created_at: "2026-01-02T00:00:00Z",
    started_at: "2026-01-02T00:00:05Z",
    completed_at: "2026-01-02T00:00:12Z",
    duration_seconds: 7,
    failure_message: null,
    exit_code: 0,
    links: {
      self: "/api/v1/workspaces/ws_1/runs/run_1",
      events_stream: "/api/v1/workspaces/ws_1/runs/run_1/events/stream",
      events_download: "/api/v1/workspaces/ws_1/runs/run_1/events/download",
      input_download: "/api/v1/workspaces/ws_1/runs/run_1/input/download",
      output_download: "/api/v1/workspaces/ws_1/runs/run_1/output/download",
      output_metadata: "/api/v1/workspaces/ws_1/runs/run_1/output",
    },
  } as RunResource;
}

function makeComment(): DocumentCommentItem {
  return {
    id: "comment_1",
    workspaceId: "ws_1",
    documentId: "doc_1",
    body: "Looks good",
    createdAt: "2026-01-03T00:00:00Z",
    updatedAt: "2026-01-03T00:00:00Z",
    author: {
      id: "user_2",
      name: "Reviewer",
      email: "reviewer@example.com",
    },
    mentions: [],
  };
}

describe("activity model", () => {
  it("builds and sorts mixed activity items", () => {
    const items = buildActivityItems(makeDocument(), [makeRun()], [makeComment()]);

    expect(items).toHaveLength(3);
    expect(items[0].type).toBe("uploaded");
    expect(items[1].type).toBe("run");
    expect(items[2].type).toBe("comment");
  });

  it("filters activity items by comments and events", () => {
    const items = buildActivityItems(makeDocument(), [makeRun()], [makeComment()]);

    expect(filterActivityItems(items, "comments")).toHaveLength(1);
    expect(filterActivityItems(items, "events")).toHaveLength(2);
    expect(filterActivityItems(items, "all")).toHaveLength(3);
  });

  it("calculates activity counts", () => {
    const items = buildActivityItems(makeDocument(), [makeRun()], [makeComment()]);
    expect(getActivityCounts(items)).toEqual({ all: 3, comments: 1, events: 2 });
  });
});

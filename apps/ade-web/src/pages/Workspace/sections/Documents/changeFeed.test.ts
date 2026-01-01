import type { InfiniteData } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { mergeDocumentChangeIntoPages } from "./changeFeed";
import type { DocumentChangeEntry, DocumentListRow, DocumentPageResult } from "./types";

const BASE_TIME = "2024-01-01T00:00:00.000Z";

function makeRow(overrides: Partial<DocumentListRow> = {}): DocumentListRow {
  return {
    id: "doc-1",
    workspaceId: "ws-1",
    name: "Report.xlsx",
    fileType: "xlsx",
    status: "queued",
    stage: null,
    uploaderLabel: null,
    assigneeUserId: null,
    assigneeKey: null,
    tags: [],
    byteSize: 1234,
    sizeLabel: "1.2 KB",
    queueState: null,
    queueReason: null,
    mappingHealth: { attention: 0, unmapped: 0 },
    activityAt: BASE_TIME,
    createdAt: BASE_TIME,
    updatedAt: BASE_TIME,
    lastRun: null,
    lastSuccessfulRun: null,
    ...overrides,
  };
}

function makePage(documents: DocumentListRow[]): DocumentPageResult {
  return {
    items: documents,
    page: 1,
    perPage: 50,
    pageCount: 1,
    total: documents.length,
    changesCursor: "5",
  };
}

function makeData(pages: DocumentPageResult[]): InfiniteData<DocumentPageResult> {
  return {
    pages,
    pageParams: pages.map((page) => page.page),
  };
}

describe("mergeDocumentChangeIntoPages", () => {
  it("updates rows and flags refreshes when the server requests it", () => {
    const doc = makeRow({ id: "doc-1", activityAt: "2024-01-01T00:00:00.000Z" });
    const data = makeData([makePage([doc])]);

    const change: DocumentChangeEntry = {
      cursor: "10",
      type: "document.upsert",
      row: makeRow({ id: "doc-1", activityAt: "2024-01-02T00:00:00.000Z" }),
      documentId: "doc-1",
      occurredAt: "2024-01-02T00:00:00.000Z",
      matchesFilters: true,
      requiresRefresh: true,
    };

    const result = mergeDocumentChangeIntoPages(data, change);

    expect(result.updatesAvailable).toBe(true);
    expect(result.data.pages[0].items?.[0].activityAt).toBe("2024-01-02T00:00:00.000Z");
  });

  it("flags updates for off-page upserts that match filters", () => {
    const doc = makeRow({ id: "doc-1" });
    const data = makeData([makePage([doc])]);

    const change: DocumentChangeEntry = {
      cursor: "11",
      type: "document.upsert",
      row: makeRow({ id: "doc-2", name: "New.xlsx" }),
      documentId: "doc-2",
      occurredAt: "2024-01-02T00:00:00.000Z",
      matchesFilters: true,
      requiresRefresh: false,
    };

    const result = mergeDocumentChangeIntoPages(data, change);

    expect(result.applied).toBe(false);
    expect(result.updatesAvailable).toBe(true);
  });
});

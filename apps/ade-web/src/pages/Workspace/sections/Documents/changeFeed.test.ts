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
    status: "uploaded",
    uploader: null,
    assignee: null,
    tags: [],
    byteSize: 1234,
    latestResult: { attention: 0, unmapped: 0 },
    activityAt: BASE_TIME,
    createdAt: BASE_TIME,
    updatedAt: BASE_TIME,
    latestRun: null,
    latestSuccessfulRun: null,
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

  it("inserts new rows when the change can be applied safely", () => {
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

    expect(result.applied).toBe(true);
    expect(result.updatesAvailable).toBe(false);
    expect(result.data.pages[0].items?.[0].id).toBe("doc-2");
    expect(result.data.pages[0].items?.length).toBe(2);
  });

  it("inserts but still flags updates when the server requires a refresh", () => {
    const doc = makeRow({ id: "doc-1" });
    const data = makeData([makePage([doc])]);

    const change: DocumentChangeEntry = {
      cursor: "12",
      type: "document.upsert",
      row: makeRow({ id: "doc-3", name: "Refresh.xlsx" }),
      documentId: "doc-3",
      occurredAt: "2024-01-02T00:00:00.000Z",
      matchesFilters: true,
      requiresRefresh: true,
    };

    const result = mergeDocumentChangeIntoPages(data, change);

    expect(result.applied).toBe(true);
    expect(result.updatesAvailable).toBe(true);
    expect(result.data.pages[0].items?.[0].id).toBe("doc-3");
  });
});

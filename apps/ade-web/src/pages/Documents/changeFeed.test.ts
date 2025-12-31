import type { InfiniteData } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { mergeDocumentChangeIntoPages } from "./changeFeed";
import type { DocumentChangeEntry, DocumentListRow, DocumentPageResult, DocumentsFilters } from "./types";

const BASE_TIME = "2024-01-01T00:00:00.000Z";

const DEFAULT_FILTERS: DocumentsFilters = {
  statuses: [],
  fileTypes: [],
  tags: [],
  tagMode: "any",
  assignees: [],
};

function makeRow(overrides: Partial<DocumentListRow> = {}): DocumentListRow {
  return {
    id: "doc-1",
    workspace_id: "ws-1",
    name: "Report.xlsx",
    file_type: "xlsx",
    status: "queued",
    stage: null,
    uploader_label: null,
    assignee_user_id: null,
    assignee_key: null,
    tags: [],
    byte_size: 1234,
    size_label: "1.2 KB",
    queue_state: null,
    queue_reason: null,
    mapping_health: { attention: 0, unmapped: 0 },
    activity_at: BASE_TIME,
    created_at: BASE_TIME,
    updated_at: BASE_TIME,
    last_run: null,
    last_successful_run: null,
    ...overrides,
  };
}

function makePage(documents: DocumentListRow[]): DocumentPageResult {
  return {
    items: documents,
    page: 1,
    page_size: 50,
    has_next: false,
    has_previous: false,
    total: null,
    changes_cursor: "5",
  };
}

function makeData(pages: DocumentPageResult[]): InfiniteData<DocumentPageResult> {
  return {
    pages,
    pageParams: pages.map((page) => page.page),
  };
}

describe("mergeDocumentChangeIntoPages", () => {
  it("flags updates when activity_at changes under activity sort", () => {
    const doc = makeRow({ id: "doc-1", activity_at: "2024-01-01T00:00:00.000Z" });
    const data = makeData([makePage([doc])]);

    const change: DocumentChangeEntry = {
      cursor: "10",
      type: "document.upsert",
      row: makeRow({ id: "doc-1", activity_at: "2024-01-02T00:00:00.000Z" }),
      document_id: null,
      occurred_at: "2024-01-02T00:00:00.000Z",
    };

    const result = mergeDocumentChangeIntoPages(data, change, {
      filters: DEFAULT_FILTERS,
      search: "",
      sort: "-activity_at",
    });

    expect(result.updatesAvailable).toBe(true);
    expect(result.data.pages[0].items?.[0].activity_at).toBe("2024-01-02T00:00:00.000Z");
  });

  it("flags updates for off-page upserts that match filters", () => {
    const doc = makeRow({ id: "doc-1" });
    const data = makeData([makePage([doc])]);

    const change: DocumentChangeEntry = {
      cursor: "11",
      type: "document.upsert",
      row: makeRow({ id: "doc-2", name: "New.xlsx" }),
      document_id: null,
      occurred_at: "2024-01-02T00:00:00.000Z",
    };

    const result = mergeDocumentChangeIntoPages(data, change, {
      filters: DEFAULT_FILTERS,
      search: "",
      sort: "-activity_at",
    });

    expect(result.applied).toBe(false);
    expect(result.updatesAvailable).toBe(true);
  });
});

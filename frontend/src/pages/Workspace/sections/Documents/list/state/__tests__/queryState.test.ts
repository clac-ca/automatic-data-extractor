import { describe, expect, it } from "vitest";

import {
  buildDocumentsQuerySnapshot,
  canonicalizeSnapshotForViewPersistence,
  encodeSnapshotForViewPersistence,
  resolveListFiltersForApi,
} from "../queryState";

describe("queryState", () => {
  it("coerces malformed sort and filters values to safe defaults", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: "  ",
      sort: { id: "createdAt", desc: true },
      filters: { id: "assigneeId", operator: "isAnyOf", value: ["me"] },
      joinOperator: "invalid",
      filterFlag: "unknown",
      lifecycle: "wrong",
      simpleFilters: {
        assigneeId: null,
      },
    });

    expect(snapshot.q).toBeNull();
    expect(snapshot.sort).toEqual([]);
    expect(snapshot.filters).toEqual([]);
    expect(snapshot.joinOperator).toBe("and");
    expect(snapshot.filterFlag).toBeNull();
    expect(snapshot.lifecycle).toBe("active");
  });

  it("resolves assigneeId=me in simple mode for API payloads", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: null,
      sort: [],
      filters: [],
      joinOperator: "and",
      filterFlag: null,
      lifecycle: "active",
      simpleFilters: {
        assigneeId: ["me"],
      },
    });

    const result = resolveListFiltersForApi({
      snapshot,
      filterMode: "simple",
      currentUserId: "user-123",
    });

    expect(result.joinOperator).toBe("and");
    expect(result.filters).toEqual([
      {
        id: "assigneeId",
        operator: "inArray",
        value: ["user-123"],
      },
    ]);
  });

  it("normalizes advanced and simple snapshots for persistence", () => {
    const advancedSnapshot = buildDocumentsQuerySnapshot({
      q: "abc",
      sort: [{ id: "createdAt", desc: true }],
      filters: [{ id: "name", operator: "contains", value: "report" }],
      joinOperator: "or",
      filterFlag: "advancedFilters",
      lifecycle: "active",
      simpleFilters: {
        assigneeId: ["me"],
      },
    });
    const simpleSnapshot = buildDocumentsQuerySnapshot({
      q: "abc",
      sort: [{ id: "createdAt", desc: true }],
      filters: [{ id: "name", operator: "contains", value: "report" }],
      joinOperator: "or",
      filterFlag: null,
      lifecycle: "active",
      simpleFilters: {
        assigneeId: ["me"],
      },
    });

    expect(canonicalizeSnapshotForViewPersistence(advancedSnapshot).simpleFilters).toEqual({});
    expect(canonicalizeSnapshotForViewPersistence(simpleSnapshot).filters).toEqual([]);
    expect(canonicalizeSnapshotForViewPersistence(simpleSnapshot).joinOperator).toBe("and");
    expect(canonicalizeSnapshotForViewPersistence(simpleSnapshot).filterFlag).toBeNull();
  });

  it("encodes current user assignee values back to me when saving views", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: null,
      sort: [],
      filters: [],
      joinOperator: "and",
      filterFlag: null,
      lifecycle: "active",
      simpleFilters: {
        assigneeId: ["user-123", "__empty__"],
      },
    });

    const encoded = encodeSnapshotForViewPersistence({
      snapshot,
      currentUserId: "user-123",
    });

    expect(encoded.simpleFilters).toEqual({
      assigneeId: ["me", "__empty__"],
    });
  });
});

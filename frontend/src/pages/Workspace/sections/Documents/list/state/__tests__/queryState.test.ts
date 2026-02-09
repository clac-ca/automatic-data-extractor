import { describe, expect, it } from "vitest";

import {
  buildDocumentsQuerySnapshot,
  canonicalizeSnapshotForViewPersistence,
  encodeSnapshotForViewPersistence,
  parseViewQueryStateToSnapshot,
  resolveListFiltersForApi,
} from "../queryState";

describe("queryState", () => {
  it("coerces malformed sort and filters values to safe defaults", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: "  ",
      sort: { id: "createdAt", desc: true },
      filters: { id: "assigneeId", operator: "isAnyOf", value: ["me"] },
      joinOperator: "invalid",
      lifecycle: "wrong",
    });

    expect(snapshot.q).toBeNull();
    expect(snapshot.sort).toEqual([]);
    expect(snapshot.filters).toEqual([]);
    expect(snapshot.joinOperator).toBe("and");
    expect(snapshot.lifecycle).toBe("active");
  });

  it("resolves assigneeId=me in filters payload", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: null,
      sort: [],
      filters: [{ id: "assigneeId", operator: "inArray", value: ["me"] }],
      joinOperator: "and",
      lifecycle: "active",
    });

    const result = resolveListFiltersForApi({
      snapshot,
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

  it("normalizes empty-filter snapshots for view persistence", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: "abc",
      sort: [{ id: "createdAt", desc: true }],
      filters: [],
      joinOperator: "or",
      lifecycle: "active",
    });

    expect(canonicalizeSnapshotForViewPersistence(snapshot).joinOperator).toBe("and");
  });

  it("encodes current user assignee values back to me when saving views", () => {
    const snapshot = buildDocumentsQuerySnapshot({
      q: null,
      sort: [],
      filters: [{ id: "assigneeId", operator: "inArray", value: ["user-123", "other"] }],
      joinOperator: "and",
      lifecycle: "active",
    });

    const encoded = encodeSnapshotForViewPersistence({
      snapshot,
      currentUserId: "user-123",
    });

    expect(encoded.filters).toEqual([
      {
        id: "assigneeId",
        operator: "inArray",
        value: ["me", "other"],
      },
    ]);
    expect((encoded as Record<string, unknown>).filterFlag).toBeUndefined();
    expect((encoded as Record<string, unknown>).simpleFilters).toBeUndefined();
  });

  it("parses persisted view query state", () => {
    const snapshot = parseViewQueryStateToSnapshot({
      q: "sales",
      sort: [{ id: "createdAt", desc: true }],
      filters: [{ id: "name", operator: "contains", value: "Q4" }],
      joinOperator: "or",
      lifecycle: "deleted",
    });

    expect(snapshot).toEqual({
      q: "sales",
      sort: [{ id: "createdAt", desc: true }],
      filters: [{ id: "name", operator: "contains", value: "Q4" }],
      joinOperator: "or",
      lifecycle: "deleted",
    });
  });
});

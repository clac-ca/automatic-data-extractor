import { describe, expect, it, vi } from "vitest";

import { clampPageSize, collectAllPages, MAX_PAGE_SIZE } from "../pagination";

describe("pagination helpers", () => {
  it("clamps page sizes to the configured maximum", () => {
    expect(clampPageSize(10)).toBe(10);
    expect(clampPageSize(MAX_PAGE_SIZE + 50)).toBe(MAX_PAGE_SIZE);
    expect(clampPageSize(0)).toBeUndefined();
    expect(clampPageSize(undefined)).toBeUndefined();
  });

  it("collects items across pages until the final page", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        items: [1, 2],
        meta: {
          limit: 2,
          hasMore: true,
          nextCursor: "next",
          totalIncluded: false,
          totalCount: null,
          changesCursor: "0",
        },
      })
      .mockResolvedValueOnce({
        items: [3, 4],
        meta: {
          limit: 2,
          hasMore: false,
          nextCursor: null,
          totalIncluded: false,
          totalCount: null,
          changesCursor: "0",
        },
      });

    const result = await collectAllPages(fetchPage);

    expect(fetchPage).toHaveBeenCalledTimes(2);
    expect(fetchPage).toHaveBeenNthCalledWith(1, null);
    expect(fetchPage).toHaveBeenNthCalledWith(2, "next");
    expect(result.items).toEqual([1, 2, 3, 4]);
    expect(result.meta.hasMore).toBe(false);
    expect(result.meta.nextCursor).toBe(null);
    expect(result.meta.limit).toBe(2);
  });
});

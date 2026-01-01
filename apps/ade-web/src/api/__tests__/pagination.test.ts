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
        page: 1,
        perPage: 2,
        pageCount: 2,
        total: 4,
        changesCursor: "0",
      })
      .mockResolvedValueOnce({
        items: [3, 4],
        page: 2,
        perPage: 2,
        pageCount: 2,
        total: 4,
        changesCursor: "0",
      });

    const result = await collectAllPages(fetchPage);

    expect(fetchPage).toHaveBeenCalledTimes(2);
    expect(result.items).toEqual([1, 2, 3, 4]);
    expect(result.page).toBe(1);
    expect(result.pageCount).toBe(1);
    expect(result.perPage).toBe(2);
    expect(result.total).toBe(4);
  });
});

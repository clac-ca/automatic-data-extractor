import { describe, expect, it, vi } from "vitest";

import { clampPageSize, collectAllPages, MAX_PAGE_SIZE } from "../pagination";

describe("pagination helpers", () => {
  it("clamps page sizes to the configured maximum", () => {
    expect(clampPageSize(10)).toBe(10);
    expect(clampPageSize(MAX_PAGE_SIZE + 50)).toBe(MAX_PAGE_SIZE);
    expect(clampPageSize(0)).toBeUndefined();
    expect(clampPageSize(undefined)).toBeUndefined();
  });

  it("collects items across pages until has_next is false", async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        items: [1, 2],
        page: 1,
        page_size: 2,
        has_next: true,
        has_previous: false,
        total: 4,
      })
      .mockResolvedValueOnce({
        items: [3, 4],
        page: 2,
        page_size: 2,
        has_next: false,
        has_previous: true,
        total: 4,
      });

    const result = await collectAllPages(fetchPage);

    expect(fetchPage).toHaveBeenCalledTimes(2);
    expect(result.items).toEqual([1, 2, 3, 4]);
    expect(result.has_next).toBe(false);
    expect(result.page).toBe(1);
    expect(result.total).toBe(4);
  });
});

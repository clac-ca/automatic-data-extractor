import { describe, expect, it } from "vitest";

import { resolveVisibleColumnCount } from "../hooks/useDocumentPreviewModel";

describe("resolveVisibleColumnCount", () => {
  it("prefers returned preview row width when rows are present", () => {
    const visibleColumnCount = resolveVisibleColumnCount({
      previewRows: [["a", "b"], ["c", "d", "e"]],
      totalColumns: 100,
      maxColumns: 50,
    });

    expect(visibleColumnCount).toBe(3);
  });

  it("falls back to capped total columns when preview rows are empty", () => {
    const visibleColumnCount = resolveVisibleColumnCount({
      previewRows: [],
      totalColumns: 100,
      maxColumns: 50,
    });

    expect(visibleColumnCount).toBe(50);
  });

  it("returns total columns when it is below the cap and rows are empty", () => {
    const visibleColumnCount = resolveVisibleColumnCount({
      previewRows: [],
      totalColumns: 12,
      maxColumns: 50,
    });

    expect(visibleColumnCount).toBe(12);
  });
});
